/*
 * can_capture.c - CAN-Sentinel Week 1 capture program (Linux SocketCAN raw socket)
 *
 * Reads Classical CAN frames from a virtual CAN interface and prints them.
 * Optionally writes the same OBSERVED-dataset CSV schema as the Python monitor
 * (the ECU/message name columns are left empty: this program knows nothing
 * about the config; map IDs to names in Week 2 or with the Python monitor).
 *
 * Why not libpcap?  See docs/week1_fundamentals.md ("Capture method"). In short:
 * a SocketCAN raw socket hands us the kernel's struct can_frame directly,
 * needs no extra library, and is the documented way to read CAN on Linux.
 *
 * Build:  make c        (or: gcc -Wall -Wextra -O2 -o bin/can_capture c_src/can_capture.c)
 * Run:    ./bin/can_capture -i vcan0 [-n COUNT] [-o file.csv] [-q]
 * Stop:   Ctrl+C
 */
#define _GNU_SOURCE
#include <errno.h>
#include <linux/can.h>
#include <linux/can/raw.h>
#include <net/if.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

#define MAX_STD_IDS 0x800

static volatile sig_atomic_t g_stop = 0;

static void on_signal(int sig)
{
    (void)sig;
    g_stop = 1;
}

static void usage(const char *prog)
{
    fprintf(stderr,
            "Usage: %s [-i interface] [-n max_frames] [-o csv_file] [-q]\n"
            "  -i  virtual CAN interface (default vcan0; must start with 'vcan')\n"
            "  -n  stop after this many data frames (default: run until Ctrl+C)\n"
            "  -o  also save frames to this CSV file\n"
            "  -q  do not print each frame\n",
            prog);
}

static void hex_payload(const struct can_frame *f, char *out, size_t out_size, int spaced)
{
    size_t pos = 0;
    out[0] = '\0';
    for (int i = 0; i < f->can_dlc && i < 8; i++) {
        int n = snprintf(out + pos, out_size - pos, spaced && i ? " %02X" : "%02X", f->data[i]);
        if (n < 0 || (size_t)n >= out_size - pos)
            break;
        pos += (size_t)n;
    }
}

int main(int argc, char **argv)
{
    const char *ifname = "vcan0";
    const char *csv_path = NULL;
    long max_frames = 0;
    int quiet = 0;
    int opt;

    while ((opt = getopt(argc, argv, "i:n:o:qh")) != -1) {
        switch (opt) {
        case 'i': ifname = optarg; break;
        case 'n': {
            char *end = NULL;
            max_frames = strtol(optarg, &end, 10);
            if (*optarg == '\0' || *end != '\0' || max_frames < 0) {
                fprintf(stderr, "ERROR: -n expects a number >= 0\n");
                return 2;
            }
            break;
        }
        case 'o': csv_path = optarg; break;
        case 'q': quiet = 1; break;
        default: usage(argv[0]); return opt == 'h' ? 0 : 2;
        }
    }

    /* Week 1 safety rule: virtual interfaces only. */
    if (strncmp(ifname, "vcan", 4) != 0 || strlen(ifname) >= IFNAMSIZ) {
        fprintf(stderr, "ERROR: interface '%s' not allowed. Week 1 only supports vcanN interfaces.\n", ifname);
        return 2;
    }

    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = on_signal;           /* no SA_RESTART: poll() must return on Ctrl+C */
    sigemptyset(&sa.sa_mask);
    sigaction(SIGINT, &sa, NULL);
    sigaction(SIGTERM, &sa, NULL);

    int fd = socket(PF_CAN, SOCK_RAW, CAN_RAW);
    if (fd < 0) {
        fprintf(stderr, "ERROR: cannot create CAN socket: %s\n"
                        "       The kernel may lack CAN support (some containers/VMs/WSL kernels do).\n",
                strerror(errno));
        return 1;
    }

    struct ifreq ifr;
    memset(&ifr, 0, sizeof(ifr));
    strncpy(ifr.ifr_name, ifname, IFNAMSIZ - 1);
    if (ioctl(fd, SIOCGIFINDEX, &ifr) < 0) {
        if (errno == ENODEV)
            fprintf(stderr, "ERROR: interface '%s' does not exist. Create it: sudo scripts/setup_vcan.sh up\n", ifname);
        else
            fprintf(stderr, "ERROR: cannot look up interface '%s': %s\n", ifname, strerror(errno));
        close(fd);
        return 1;
    }

    struct sockaddr_can addr;
    memset(&addr, 0, sizeof(addr));
    addr.can_family = AF_CAN;
    addr.can_ifindex = ifr.ifr_ifindex;
    if (bind(fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        fprintf(stderr, "ERROR: cannot bind to '%s': %s\n", ifname, strerror(errno));
        close(fd);
        return 1;
    }

    FILE *csv = NULL;
    if (csv_path) {
        csv = fopen(csv_path, "w");
        if (!csv) {
            fprintf(stderr, "ERROR: cannot open '%s' for writing: %s\n", csv_path, strerror(errno));
            close(fd);
            return 1;
        }
        fprintf(csv, "observed_timestamp,can_id,can_id_hex,ecu_name,message_name,dlc,payload_hex,inter_arrival_s,frame_flags,source\n");
    }

    double last_seen[MAX_STD_IDS];
    for (int i = 0; i < MAX_STD_IDS; i++)
        last_seen[i] = -1.0;

    unsigned long data_frames = 0, invalid = 0, error_frames = 0;
    fprintf(stderr, "Listening on %s (Ctrl+C to stop)\n", ifname);

    struct pollfd pfd = { .fd = fd, .events = POLLIN };
    while (!g_stop && (max_frames == 0 || (long)data_frames < max_frames)) {
        int pr = poll(&pfd, 1, 500);
        if (pr < 0) {
            if (errno == EINTR)
                continue;
            fprintf(stderr, "ERROR: poll failed: %s\n", strerror(errno));
            break;
        }
        if (pr == 0)
            continue;

        struct can_frame frame;
        ssize_t n = read(fd, &frame, sizeof(frame));
        if (n < 0) {
            if (errno == EINTR || errno == EAGAIN)
                continue;
            fprintf(stderr, "ERROR: read failed: %s\n", strerror(errno));
            break;
        }

        struct timespec ts;
        clock_gettime(CLOCK_REALTIME, &ts);   /* local observation time */
        double now = (double)ts.tv_sec + (double)ts.tv_nsec / 1e9;

        if (n != (ssize_t)sizeof(frame) || frame.can_dlc > 8) {
            invalid++;
            fprintf(stderr, "WARN: ignoring invalid frame (size %zd, dlc %u)\n", n, n == (ssize_t)sizeof(frame) ? frame.can_dlc : 0u);
            continue;
        }
        if (frame.can_id & CAN_ERR_FLAG) {
            error_frames++;
            fprintf(stderr, "WARN: error frame received\n");
            continue;
        }

        int ext = (frame.can_id & CAN_EFF_FLAG) != 0;
        int rtr = (frame.can_id & CAN_RTR_FLAG) != 0;
        uint32_t id = frame.can_id & (ext ? CAN_EFF_MASK : CAN_SFF_MASK);

        double delta = -1.0;
        if (!ext) {
            if (last_seen[id] >= 0.0)
                delta = now - last_seen[id];
            last_seen[id] = now;
        }

        char spaced[32], packed[32];
        if (rtr) {
            spaced[0] = packed[0] = '\0';
        } else {
            hex_payload(&frame, spaced, sizeof(spaced), 1);
            hex_payload(&frame, packed, sizeof(packed), 0);
        }
        data_frames++;

        if (!quiet) {
            struct tm tmv;
            char stamp[16];
            time_t secs = ts.tv_sec;
            localtime_r(&secs, &tmv);
            strftime(stamp, sizeof(stamp), "%H:%M:%S", &tmv);
            printf("%s.%03ld  0x%0*X  [%u]  %-23s", stamp, ts.tv_nsec / 1000000L, ext ? 8 : 3, id, frame.can_dlc, spaced);
            if (delta >= 0.0)
                printf("  +%.1fms", delta * 1000.0);
            printf("%s%s\n", ext ? " EXT" : "", rtr ? " RTR" : "");
            fflush(stdout);
        }

        if (csv) {
            fprintf(csv, "%.6f,%u,0x%0*X,,,%u,%s,", now, id, ext ? 8 : 3, id, frame.can_dlc, packed);
            if (delta >= 0.0)
                fprintf(csv, "%.6f", delta);
            fprintf(csv, ",%s%s%s,observed:%s (c capture)\n", ext ? "EXT" : "", (ext && rtr) ? "+" : "", rtr ? "RTR" : "", ifname);
        }
    }

    fprintf(stderr, "\nCapture stopped (%s).\n", g_stop ? "interrupted" : "finished");
    fprintf(stderr, "  observed data frames : %lu\n  invalid frames       : %lu\n  error frames         : %lu\n",
            data_frames, invalid, error_frames);

    if (csv && fclose(csv) != 0)
        fprintf(stderr, "WARN: closing '%s' failed: %s\n", csv_path, strerror(errno));
    close(fd);
    return 0;
}
