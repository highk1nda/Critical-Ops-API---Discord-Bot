# Critical Ops API — Discord Bot

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![discord.py](https://img.shields.io/badge/discord.py-2.x-5865F2?logo=discord&logoColor=white)](https://discordpy.readthedocs.io/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Hosting](https://img.shields.io/badge/Hosting-Katabump%20(free)-orange)](https://katabump.com/)

> A lightweight, efficient Discord bot (codename: Syrnyk) that integrates with the Critical Ops API to fetch player stats, estimate cheater probability, manage roles, and generate stat card images.

> **Disclaimer:** This project is not affiliated with Critical Force or any other organization. It was built by the community, for the community, using publicly available information.

---

## 🕊️ Features

- **Player Stats** — Fetch detailed stats from the Critical Ops API per user request
  - Estimate cheater account probability based on fetched data
- **Stat Card Image Generation** — Renders a clean 512×512 px image of all player stats
  - Optimized for minimal CPU usage even on free hosting
- **Role Management** — Assign/remove roles via button press interactions
- **Status Reporting** — Posts bot online/offline notifications to a designated channel

---

## 📺 Workflow

![Howdy? Check my other repos for Easter eggs :D](workflow.gif)

---

## ⚙️ Prerequisites

Before installing, make sure you have:

- **Python 3.8+**
- A **Discord bot token** ([create one here](https://discord.com/developers/applications))
- Access to the **Critical Ops API** (publicly available endpoints)

---

## 📦 Installation

```bash
git clone https://github.com/highk1nda/Critical-Ops-API---Discord-Bot
cd Critical-Ops-API---Discord-Bot
```

Install dependencies:

**Windows:**
```bash
pip install discord.py python-dotenv numpy pillow aiohttp
```

**macOS / Linux:**
```bash
pip3 install discord.py python-dotenv numpy pillow aiohttp
```

---

## 🔑 Configuration

Create a `.env` file in the project root and add your Discord bot token:

```
DISCORD_TOKEN=your_token_here
```

> ⚠️ Never commit your `.env` file to version control. Add it to `.gitignore`.

To configure the **status reporting channel** and **role assignments**, edit the relevant variables at the top of `status.py` and `roles.py` respectively.

---

## 🚀 Running the Bot

```bash
python3 app.py
```

---

## 🗂️ Project Structure

```
Critical-Ops-API---Discord-Bot/
│
├── app.py                  # Entry point
├── generate_stats_card.py  # Image generation logic
├── roles.py                # Role management (button events)
├── stats.py                # API calls and stat parsing
├── status.py               # Online/offline status reporting
├── .env                    # Your Discord token (not committed)
└── README.md
```

---

## 📊 Performance

Tested on **Katabump (free hosting)**:

| Metric | Value |
|---|---|
| CPU — image rendering | ~8–11% (of 25% available) |
| CPU — API requests | ~0.4–1% (of 25% available) |
| RAM usage | ~68 MB (stable at idle and under load) |
| Storage usage | ~110 MB |
| Rendered image resolution | 512×512 px |

---

## 📈 Scalability

| Scenario | Concurrent Users |
|---|---|
| With image generation | Up to ~2 (hosting limit) |
| Without image generation | Up to ~15–17 (hosting limit) |

Current limits are a result of free hosting constraints, not the bot itself. On proper hosting, both concurrency and image resolution can be improved with minimal effort.

---

## 🔮 Roadmap

- [ ] Higher resolution stat card output on better hosting
- [ ] Additional stat categories and API endpoints
- [ ] Leaderboard / server ranking feature

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome. Feel free to open an issue or submit a pull request.

---

**Have fun, do pobachennya 👋**

[More projects by highk1nda 🚧](https://github.com/highk1nda)