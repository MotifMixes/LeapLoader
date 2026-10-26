# Updating LeapLoader

LeapLoader checks for a new version when it starts. When one is out, a green **⬆ Update to 0.2.1** button (with the new version's number) appears right after the menus.

1. Click the green button. The **Updates and patch notes** window opens and shows what's new.
2. Click **Update now**. LeapLoader downloads the new version, puts it in place of the old one and restarts by itself. (While a card is being built, **Update now** waits until the build ends.)

Your settings and your list of games are kept: they are not in the program's folder (see [Where your things are kept](02-getting-started.md#where-your-things-are-kept)). Nothing on your SD card changes; build the card again to put the new version's menu and fixes on it.

**Skip this version** stops LeapLoader announcing that version at start-up. **Later** closes the window and keeps the button for next time.

**Help › Check for updates…** opens the same window at any time and checks again. Untick **Check for updates when LeapLoader starts** there if you don't want LeapLoader to look by itself (it is on at first).

## When LeapLoader can't update itself

Sometimes LeapLoader can't put the new version in place by itself. The window then shows **Download** instead of **Update now**, and says why under it; **Download** opens the release page. This happens:

- **when it runs from inside its zip** (Windows then opens just `LeapLoader.exe`, in a temporary folder): unzip all of it to a folder (right-click the zip, **Extract All…**) and start LeapLoader from there.
- **in a build from source**: update the source and build it again.

If **Update now** starts but the update can't be put in place (LeapLoader can't write to its folder, for example), the window says **The update didn't install** and why, and nothing is changed. Move the `LeapLoader` folder to one that is yours (your Desktop or Documents, for example) and try again, or click **Download it from GitHub instead**. On macOS this also happens when **LeapLoader.app** was opened straight from the download (macOS then runs a read-only copy): move it to Applications, open it from there and update again.

**From LeapLoader 0.1.0**, which had no updater, there is no button: download the new version by hand once (below). Every later version can update itself.

To update by hand, download the file for your system from the [releases page](https://github.com/MotifMixes/LeapLoader/releases/latest) (see [Getting started](02-getting-started.md#installing)), close LeapLoader, and put the new version in place of the old one: on Windows and Linux, unpack it over your old `LeapLoader` folder; on macOS, drag the new **LeapLoader.app** to Applications and replace the old one.

## Patch notes

The **Updates and patch notes** window lists what every version brought, newest first.
