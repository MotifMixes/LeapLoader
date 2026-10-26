# Leapster 2 over USB (beta)

LeapLoader can build the card straight onto a Leapster 2's SD card through the console's USB cable, without taking the card out. It's in the **🔌  Leapster 2 over USB** box at the bottom right, marked **Beta**.

> **This has not been tried on a real Leapster 2 yet.** It works with the Ribbit emulator's Leapster 2, but a real console may answer differently. If you try it, please send the USB log (below): it is what tells us whether it works. Copy the SD card's files somewhere first.

The other way, taking the card out and using the PC's card reader, is described in [Building the card](04-building-the-card.md) and doesn't need any of this.

## What you need

- A **Leapster 2** with an SD card in it, and its USB cable.
- Some games switched on in the list.
- Admin rights on the PC: Windows asks for them when the card is opened and when it is ejected.

## Steps

1. Turn the Leapster 2 on and plug it into the PC with its USB cable. Wait until it shows its "connected" screen.
2. Click **Look for a Leapster 2**. It should show **✔ Leapster 2 SD card** (and maybe its internal storage, which is only shown, never opened or written). If it says **No Leapster 2 found**, check the cable and the "connected" screen and look again.
3. Click **Open the SD card…**, read the question and click **Open it**. Say **Yes** to Windows' admin prompt. LeapLoader sends the console its "mount" command, as LeapFrog's own software does. Within about 30 seconds the SD card appears as a drive (for example `E:\`), and LeapLoader says where.
4. Click **Build card onto the Leapster 2**, read the question (it names the drive and the free room) and click **Build onto it**. Wait for the bar to finish.
5. Click **Eject the Leapster 2…**, then **Eject**, and say **Yes** to the admin prompt again. LeapLoader makes sure everything is written, closes the drive and tells the console it can go.
6. Unplug the Leapster 2 and tap its SD icon (see [On the Leapster 2](05-on-the-leapster-2.md)).

## What LeapLoader will and won't do

- It only sends commands to a disk that says it is a **LeapFrog Leapster 2** disk, and checks again before each command. Every other disk is only looked at (its name), never written.
- Each step that changes something (opening the card, building onto it, ejecting) asks you first.
- It copies files onto the card as into any folder. It never formats or repartitions anything.

## The USB log

The log lists every disk LeapLoader saw and why it did or didn't pick it, every command sent to the console with its answer, how long things took, and the drive that appeared. It holds no personal files, only disk names and drive letters.

- **Copy USB log** copies it, to paste into a report.
- **Save USB log** saves `usb-log.txt` in LeapLoader's data folder (`%APPDATA%\LeapLoader`) and opens the folder.

Please send it with your Leapster 2's BIOS version if you know it, your Windows version, and what happened at each step. `TESTING-USB.txt` in the LeapLoader folder has the same steps.

## If something goes wrong

| Message | What to do |
|---|---|
| **needs admin rights** | The admin prompt was answered No. Try again and say Yes |
| **refused mount** or **didn't become ready** | The message has the console's answer. Check that an SD card is in the console, and send the log |
| **no drive appeared** | Look in File Explorer for a new drive. If it's there, click **Look for a Leapster 2** again. Send the log either way |
| Eject failed | Close any windows showing the SD card's files, then try **Eject** again |
