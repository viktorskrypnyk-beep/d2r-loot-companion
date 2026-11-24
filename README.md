# D2R Loot Companion
### Your personal loot assistant for Diablo II: Resurrected

**English** · [Українська](README_UA.md)

Diablo II: Resurrected is a game of exciting discoveries—and difficult decisions. After a run, you may be staring at a collection of rare, unique and set items, charms, jewels, and runes, trying to remember which rolls matter and whether that one unusual drop is worth keeping. **D2R Loot Companion** is a Windows desktop project designed to take some of that busywork off your hands.

The idea is simple: **take a screenshot, understand your drop, and make a better decision without leaving your game for a dozen browser tabs.** The app combines screenshot capture, AI-assisted recognition, a personal item collection, comparison tools, and rune/runeword reference features.

> **Project status:** Early, actively developed desktop application (archive version 0.6). It is a player-created helper, not an official Blizzard application. Features, recognition quality, and interfaces may change.

## Why we are building it

Every D2R player eventually runs into the same questions: *Is this rare item actually good? Should I keep two copies? Is this useful for a character I plan to level later? Which runes do I already have? How many items did I find during this farming session?*

We want one practical place to answer those questions. The goal is not to play the game for you, automate gameplay, or promise a perfect market valuation. It is to help you **organize information and spend more time playing**.

## What is in the current project

### Screenshot capture and an item-review queue
Capture an item tooltip or import screenshots for analysis. A single run may produce several interesting drops, so the interface is designed around processing more than one item, rather than forcing you to finish with the first screenshot before taking another. The capture workflow and preview allow you to inspect what is being sent for recognition.

### AI-assisted item recognition
The app integrates with **Google Gemini** to interpret item screenshots and extract useful item information. This is an assistant, not an infallible judge: stylized fonts, tooltips, partially covered text, unusual affixes, and image quality can all cause mistakes. Always double-check important details before selling or deleting valuable items. You configure your own API access; **never commit an API key to GitHub**.

### Your own collection, not just a temporary result
Keep track of interesting loot in a personal catalog. The project includes item-oriented storage, detail views, filtering and comparison workflows. The long-term aim is a searchable collection that makes it easy to answer: “Do I already own something better?”

### Runs, finds, and progression
The project distinguishes collected items from finds during a farming run. It includes run-related views and history, helping you review loot after a session rather than interrupting every fight to make a decision.

### Runes and runewords
A rune reference covering the classic **33 runes**, plus a runeword catalog, helps plan what to assemble next. The intention is to make recipes and missing ingredients easy to understand. Always verify the item base, exact number of sockets, order of insertion, game mode, and character requirements before using expensive runes.

### A desktop-first interface
The codebase is written in **Python** and uses a **PySide6 / Qt** graphical interface. The current project includes Windows launch helpers, a demo mode, application settings, localization support, preview screenshots, and automated tests.

### Character and collection context
Game modes and collections matter: Ladder and non-Ladder gear should not be mixed accidentally, and the Reign of the Warlock edition introduces its own context. The project is evolving to provide clearer separation and filtering of relevant inventories.

## A typical workflow

1. Play D2R normally and pick up an item that looks interesting.
2. Capture its tooltip or import an existing screenshot.
3. Inspect the capture and submit it to the recognition workflow.
4. Review the extracted item name, type, and properties. Fix anything that the AI misunderstood.
5. Compare the result with what you already own.
6. Keep the item in your collection, mark it for review, or decide that it is not worth saving.
7. Repeat with the next find—and review the entire run later.

This is how we want the tool to feel: **fast enough to use between fights, clear enough for a newer player, and detailed enough to grow with an experienced one**.

## Getting started (development build)

This repository is intended for the source code of the Python application. On Windows, use a recent Python version and install the requirements:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Launch helpers such as `Start-Windows.bat` and `Demo-Windows.bat` are part of the prepared source archive. For recognition, configure your own Google Gemini API key in the application's settings. A network connection and any applicable provider charges may be required. The exact setup may change as the project evolves.

## Roadmap — where we want to go next

The following items are **plans and areas of improvement**, not promises that every feature already works perfectly.

**1. Faster, more dependable capture.** Improve clipboard monitoring, hotkeys, multi-monitor capture, and the multi-screenshot queue. Make it easy to close a preview and wait for the next item without losing previously queued captures.

**2. Recognition you can trust.** Improve reading of item names, affixes, sockets, ethereal flags, variable rolls, and rune numbers. Highlight uncertainty instead of inventing stats; let players correct a result before saving it.

**3. A genuinely useful “Keep or Sell?” assistant.** Compare an item against known rolls and alternatives, explain *why* it could be valuable, and distinguish usefulness for a build from trade value. Recommendations should be transparent and adjustable, not unexplained verdicts.

**4. Better collection management.** Make rare, unique and set items easier to browse; improve search, sorting, thumbnail previews, comparisons, duplicate detection, delete/undo operations, and safe backups.

**5. Rune and runeword planning.** Count owned runes, simplify adding quantities, flag missing components, show valid socketed bases, and prevent expensive mistakes before the user inserts runes.

**6. Build-aware decisions.** Let players specify class, level, skills, and equipment goals—for example a Whirlwind Barbarian or Lightning Fury Amazon—so advice takes the actual character into account.

**7. Farming-session analytics.** Record finds by run, track useful drops and progress, and make it easier to look back on a session.

**8. UI polish and performance.** Reduce lag in rune inputs and large collections, move frequently used actions closer to where they are needed, simplify screen layout, and improve progress and error messages.

**9. Easier Windows distribution.** Build a portable or installer-based Windows release so players do not have to install Python, with clear upgrade and backup paths.

**10. Documentation, testing and community feedback.** Add illustrated tutorials, sample screenshots, issue templates, regression tests, and a clear process for reporting recognition errors and requesting features.

## Privacy, security and fair use

- Avoid uploading screenshots that contain personal information.
- API credentials belong in local settings, not source control or public screenshots.
- AI recognition can be wrong; review recommendations before taking irreversible action.
- Artwork, item names, and other Diablo-related intellectual property belong to their respective owners. This project is unofficial and is not endorsed by Blizzard Entertainment.
- We want a companion for understanding your loot, **not a bot that plays, trades, or modifies the game automatically**.

## Feedback and contributions

If you discover a recognition error or want to suggest a feature, open a GitHub issue with the expected result, what happened, and a screenshot **with private information removed**. Practical player feedback is what will make this tool genuinely useful.

**The vision:** less time managing drops, more time enjoying the hunt.
