# Week 1 Fundamentals: CAN in Plain English

Everything below is simplified for learning. The ECU names, IDs and payloads used in this project are **illustrative inventions for a lab**, not a verified real-vehicle protocol. You do not need a car or a physical ECU.

## 1. Automotive cybersecurity
Modern cars are networks of small computers. Automotive cybersecurity is about stopping attackers from sending harmful or misleading messages on those networks (for example, fake sensor readings), and about detecting it when they do.

## 2. ECU (Electronic Control Unit)
A small embedded computer that controls one function: engine, dashboard, battery monitoring, and so on. A car can have dozens.

## 3. CAN bus
CAN (Controller Area Network) is a shared two-wire bus. Every ECU is connected to it and **every ECU hears every message**. It is robust and cheap, which is why cars use it. Classical CAN has no built-in authentication, which is exactly why intrusion detection is interesting.

## 4. Why ECUs exchange messages
The dashboard needs engine speed to show on the gauge, the engine controller needs the coolant temperature, and so on. Instead of dedicated wires, each ECU periodically broadcasts its values on the bus.

## 5. CAN frame
One message on the bus. A Classical CAN data frame, at a high level:

```
| ID (11 bits) | control + data length | payload (0-8 bytes) | CRC, ACK, etc. |
```
Your programs only see the parts the kernel exposes: the ID, the data length and the payload (the CRC/ACK part is handled by hardware and does not exist on `vcan0`).

## 6. CAN identifier (arbitration ID)
Names *what the message is* (e.g. "engine status"), not who receives it. It also decides priority: when two ECUs transmit at the same time, the **lower ID wins** the bus. A standard ID is 11 bits: `0x000` to `0x7FF`.

## 7. Payload
The data bytes. Their meaning is defined by the vehicle maker. In our lab, for the invented ID `0x100`:
```
byte 0-1  rpm (big-endian)     byte 2  throttle %     byte 3  load %     byte 7  rolling counter
```

## 8. Data length (DLC)
How many payload bytes the frame carries: 0 to 8 in Classical CAN. Example: `0x200` carries 4 bytes.

## 9. Timestamp
The moment a frame was sent or observed, according to a clock. The simulator records its send time; a monitor records its own observation time. They differ slightly, and that is normal.

## 10. Frequency and inter-arrival time
Most CAN messages repeat periodically. A message every 100 ms has a frequency of 10 Hz. The *inter-arrival time* is the gap between two consecutive frames with the same ID (~100 ms). Attacks often change these gaps, which makes it a key feature for Week 2.

## 11. SocketCAN
The Linux kernel's CAN framework. It makes CAN interfaces look like network interfaces and lets programs read/write frames through sockets (`AF_CAN`).

## 12. Virtual CAN interface
A software-only CAN interface: whatever one program writes appears to every other program reading that interface. No wires, no hardware.

## 13. What `vcan0` means
`vcan` is the virtual CAN driver, and `0` is the first instance. Names like `vcan1` also work. A physical adapter would appear as `can0`; this project **refuses** anything other than `vcanN` on purpose.

## 14. Virtual vs physical CAN
| | `vcan0` | Real vehicle bus |
|---|---|---|
| Wires/electrical signalling | none | yes |
| Bit rate / bus errors / arbitration | not simulated | real |
| Message timing | OS scheduling | hardware-timed |
| ACK / CRC | not present | present |
| Safety risk | none | can affect a vehicle |

So `vcan0` is perfect for learning and software testing, but it is not proof of how a real vehicle behaves.

## 15. Normal traffic in this project
Synthetic, well-behaved traffic: a fixed set of IDs, each repeating at a steady interval, constant payload length, and values that change by small steps. Reproducible from a random seed.

## 16. Why a baseline first
Anomaly detection means "this looks different from usual". Without a trustworthy record of *usual*, you cannot tell an attack from normal variation, and you cannot measure false alarms. Week 1's dataset is that record.

## Illustrative diagram (simulation only)

```
 ┌──────────────┐   0x100 every 100 ms    ┌──────────────┐
 │ Engine ECU   │ ──────────────────────► │              │
 │ (simulated)  │                         │              │
 └──────────────┘                         │    vcan0     │      ┌──────────────┐
 ┌──────────────┐   0x200 every 200 ms    │ (virtual bus │ ───► │ Monitor      │
 │ Dashboard ECU│ ──────────────────────► │  in kernel)  │      │ (observer)   │
 │ (simulated)  │                         │              │      └──────────────┘
 └──────────────┘                         └──────────────┘
```

## Worked frame example
`cansend vcan0 123#DEADBEEF` means: ID `0x123`, 4 data bytes `DE AD BE EF`. `candump` shows it as `vcan0  123   [4]  DE AD BE EF`. Another valid example: `cansend vcan0 7FF#00` (highest standard ID, 1 byte).

## Capture method: libpcap vs a SocketCAN raw socket
The project proposal mentions C with libpcap. libpcap is a general packet-capture library built for network interfaces such as Ethernet. Whether it can read CAN interfaces depends on how your libpcap was built and which version you have, and I have **not verified libpcap capture on `vcan0`** on any machine, so this repo does not rely on it.

Instead, `c_src/can_capture.c` uses a **SocketCAN raw socket**, the documented Linux way to read CAN: it needs no extra library, and gives the kernel's `struct can_frame` (ID, length, payload) directly, which is exactly what we need to validate and save. It is a compatible alternative to the proposed method for the same goal (capture frames from `vcan0`).

If you want to experiment with libpcap, you can optionally try `sudo apt install tcpdump` then `sudo tcpdump -i vcan0 -c 5` while the simulator runs, and record what you see in `docs/week1_progress.md`. That is optional and not required for Week 1.

**Python vs C monitors:** the Python monitor is the main tool (config-aware, writes the dataset). The C program demonstrates the project's C requirement and a lower-level approach. Both read the same interface independently; neither is required for the other to work.
