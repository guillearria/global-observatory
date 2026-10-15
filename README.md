# Global Observatory

A website that keeps track of major world events, long-term threats to humanity, and the worst
disasters in history.

**[Open the site →](https://guillearria.github.io/global-observatory/)**

## What's on the site

The site has three sections:

- **World Pulse** follows major events as they happen, such as earthquakes, floods, wildfires,
  storms, disease outbreaks and wars. Every event is marked on a world map, and its page links to
  the official source that keeps the latest numbers.
- **Existential Threats** covers long-term risks to humanity, such as climate change, nuclear war,
  pandemics and asteroid impacts. Each threat has a simple rating for how likely and how severe it
  is, along with the published figures and sources behind it.
- **Historical Archive** collects the worst disasters in history, from the ancient world to recent
  times. It includes pandemics, wars, famines, natural disasters and the collapse of whole
  civilizations, in date order.

The site collects figures that official sources have already published. It does not make
forecasts of its own.

## Who writes it

An AI (Claude, made by Anthropic) does the research and the writing. Every day it looks for new
major events and updates the ones already on the site. Once a week it reviews the long-term
threats, and the archive grows from time to time.

The AI does not decide what counts as a confirmed fact. A separate program makes that call, and it
applies the same fixed rules every time.

## How facts are checked

Every number on the site links to the source it came from. Before anything is published, the
checking program looks at each link and confirms that it leads to an organization on an approved
list. The list includes the World Health Organization, the US Geological Survey, NASA and the
United Nations, along with sources for history such as Encyclopaedia Britannica, the Smithsonian,
national archives and university presses. Wikipedia is not on the list.

If the main numbers in a record can't be traced to an approved source, the site doesn't present it
as confirmed. The record is held back, or shown in a separate "Under review" area with a clear
warning.

The AI is allowed to add a new organization to the approved list, so it does have some say over
which sources count as trusted. To keep that honest, each addition needs a written reason and is
recorded publicly in the [changelog](CHANGELOG.md). The AI cannot change the rules that do the
checking.

## What the check can't do

The program confirms that each number links to a trusted source, but it can't read the source to
make sure the number matches. That part depends on the research. The AI is told to open every
source and copy each number from it, and to mark a number as unconfirmed whenever it can't.

## Keeping it current

The site updates itself. If the daily updates ever stop, visitors see a warning on the site, and an
automatic daily check flags the problem.

Every change is saved in this repository's history, so anyone can look back and see what changed
and when.

## Who made this

Global Observatory is a personal project by [Guillermo Arria-Devoe](https://github.com/guillearria).
It's meant to show that an AI can keep a public website up to date on its own, as long as something
other than the AI decides what counts as a confirmed fact.

Questions and corrections are welcome. You can
[open an issue](https://github.com/guillearria/global-observatory/issues), and
[CONTRIBUTING.md](CONTRIBUTING.md) explains how to add a record or suggest a new source.

## For developers

The [technical overview](docs/TECHNICAL-OVERVIEW.md) explains how records are stored and checked,
how to run the project on your own computer, and how each data file is laid out. The full design
is in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
