# Testing LeapLoader with a Leapster 2 over USB

Thank you for testing. LeapLoader can put games straight onto a Leapster 2's SD card over its USB
cable, without taking the card out. This part has **not been tried on a real console yet**: your
USB log is what tells us whether it works.

## What you need

- A **Leapster 2** (not the first Leapster or the Leapster L-MAX: they have no SD card) with an SD
  card in it, and its USB cable.
- Windows 10/11 or Linux. (macOS can't do this yet.)
- LeapLoader, and some game dumps added to its list.

It's a good idea to copy the SD card's files somewhere first, in case something goes wrong.

## Steps

1. Turn the Leapster 2 on and plug it into the PC with its USB cable. Wait until it shows its
   "connected" screen.
2. In LeapLoader, in **Leapster 2 over USB** (bottom right), click **Look for a Leapster 2**.
   - You should see "✔ Leapster 2 SD card" (and maybe "internal storage").
   - If it says "No Leapster 2 found", click **Save USB log** and send us the file anyway.
3. Click **Open the SD card…**, read the question, click **Open it**.
   - Windows shows its admin prompt (Linux: a password prompt). Say **Yes**: LeapLoader needs
     admin rights for this step only, to send the console its "mount" command.
   - Wait up to 30 seconds. The SD card should appear as a drive (for example `E:\`), and LeapLoader
     shows where.
4. Click **Build card onto the Leapster 2**, read the question (it names the drive), click
   **Build onto it**. Wait for the progress bar to finish.
5. Click **Eject the Leapster 2…**, then **Eject**, and say **Yes** to the admin prompt again.
   LeapLoader writes everything to the card, closes the drive and tells the console it can go.
6. Unplug the Leapster 2 and try the games from its SD icon.

## What to send back

- The **USB log**: click **Save USB log** (it opens the folder with `usb-log.txt`), or **Copy USB
  log** and paste it. It lists every disk LeapLoader saw and why it did or didn't pick it, every
  command sent to the console with its answer, how long things took, and the drive that appeared.
  It has no personal files, just disk names and drive letters.
- Your **Leapster 2's BIOS version** if you know it, and your Windows or Linux version.
- What happened at each step, and whether the games started on the console.

## What LeapLoader will and won't do

- It only ever sends commands to a disk that says it is a **LeapFrog Leapster 2** disk, and asks it
  again before each command. Every other disk is only looked at (its name), never written.
- Each step that changes something (opening the card, building onto it, ejecting) asks you first.
- It copies files onto the card like into any folder. It never formats or repartitions anything.
- The console's internal storage is only shown, not opened or written.

## If something goes wrong

- **"needs admin rights"**: the admin prompt was answered No, or (Linux) `pkexec` is missing. On
  Linux you can start LeapLoader with `sudo` instead.
- **"refused mount"** or **"didn't become ready"**: the message has the console's answer (SCSI sense
  data). Check that an SD card is in the console and send the log.
- **"no drive appeared"**: look in your file manager for a new drive; if it is there, click
  **Look for a Leapster 2** again. Send the log either way.
- **Eject failed**: close any windows showing the SD card's files, then try Eject again.
