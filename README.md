# ME/CFS Recovery Planner

**[Support my work on Buy Me a Coffee](https://buymeacoffee.com/dkjroot)**

**Free to use. Please help keep it that way.**

I want this to be freely available to anyone who finds it useful. Please keep
it free if you share it or run it for other people. The code is released under
the [GNU General Public License v3](LICENSE).

I'm starting this for someone close to me who has ME/CFS. The idea is to make
a simple web app that helps you keep your plans in one place and take things
day by day. I plan to draw on material from [CFS Health](https://www.cfshealth.com/home). I think it's only fair if
you use this app that you buy his ebook!

## Medical disclaimer

I'm not a doctor. I built this planner to help you organise your plans. Use
it at your own risk and alongside advice from your healthcare professional.
Talk to them before making any changes to your care or treatment.

## Getting started

You'll need Python 3.10 or newer. There are no Python packages to install.

Open a terminal in the project folder. Create the first account, then start
the planner. The account command asks for a passphrase without showing it
as you type. Use at least 12 characters.

**Windows (PowerShell)**

```powershell
.\run.ps1 --add-user Mama
.\run.ps1
```

The launcher uses the Windows Python launcher (`py`) or an existing Python
3.11 installation managed by `uv`.

**macOS**

```bash
chmod +x run.command
./run.command --add-user Mama
./run.command
```

After the first command, you can also double-click `run.command` in Finder.

**Linux (including Raspberry Pi OS)**

```bash
sh ./run.sh --add-user Mama
sh ./run.sh
```

Open [http://127.0.0.1:8022](http://127.0.0.1:8022) in a browser on the
computer running the app. Press `Ctrl+C` in the terminal to stop it. If port
8022 is already in use, add `--port 8080` to the start command and open
[http://127.0.0.1:8080](http://127.0.0.1:8080) instead.

If you’ve just updated the planner, close the old server before starting
it again. Open the address printed by the launcher. Opening
`web/index.html` by itself won’t connect to the planner.

Sign in with the username and passphrase you set up. On your own device,
tick **Keep me signed in for 30 days** to stay signed in when you close the
browser. Use **Sign out** when you’re done on a shared device.

### Managing accounts on the host

To add someone else, run `--add-user` with their chosen username. To change
a forgotten passphrase, run `--reset-password Mama` in the same way. That
also signs out browsers using the old login. Each account has its own
planner. Account management is done from the terminal on the host.

If you used an earlier copy of the planner, stop the server and run
`--import-planner Mama` to copy the old plan and check-ins into Mama’s
account. The original file is kept, and the command only imports into an
account with no planner data yet.

### Access over a VPN

Keep the planner listening on `127.0.0.1`. Set your VPN-only HTTPS reverse
proxy to forward to `http://127.0.0.1:8022` and preserve the browser’s
`Host` header. Start the app with the same HTTPS address the browser uses.
For example, replace `planner.example.net` with your private hostname.

**Windows (PowerShell)**

```powershell
.\run.ps1 --https-origin https://planner.example.net
```

**Linux**

```bash
sh ./run.sh --https-origin https://planner.example.net
```

Open that HTTPS address while connected to the VPN. This enables secure
sign-in cookies.

## Using the planner

When you first sign in, answer five quick questions about your current
capacity (for example, how you tolerate household tasks, mental focus, and
a 10-minute flat walk). The planner places you conservatively along a
three-phase, twelve-level roadmap—from **Restore & Stabilize** (Levels 1–4),
through **Rebuild & Strengthen** (Levels 5–8), to **Re-integrate into Life**
(Levels 9–12)—and projects dates forward toward normal energy.

Each day in **Today**, your routine is already filled in for your current
level (rest, everyday home tasks, walking, gentle movement/stretching,
reading or mental focus, and social time). Use the quick radio buttons to
mark how each felt (`Skipped`, `Too much`, `Just right`, or `Could do more`)
along with how you felt overall, any extra energy drainers, and any
unplanned activities beyond the plan.

- **Stepping up:** Once you complete the steady hold window for a level (and
  any 3-day follow-up window after an unplanned exertion clears), the planner
  asks whether you are ready to move to the next level or hold for five more
  days and recalculate dates.
- **Crashes & stabilization:** Logging a crash (or two consecutive worse days)
  automatically switches to a stripped-back stabilization routine. After two
  consecutive steady days, the planner suggests a safe return level—factoring
  in whether an unplanned stressor preceded the dip and any recent setbacks—and
  adjusts future stage dates on the **Journey** trajectory graph.
- **Your choices:** Under **Plan**, you can toggle optional activities on or
  off, change your hold-window pace, jump to any level, or retake the starting
  assessment.

Plans and check-ins are saved as separate JSON files on the computer
running the planner. The `local_data` folder also contains a small SQLite
database with accounts, password hashes and sign-in sessions. The planner
files are readable by anyone with access to that folder on the host.

### Free to use. Please help keep it that way.

I develop this project to be freely available to everyone, supported, if at all, by voluntary contributions. I do not want other people to profit from my work by selling copies, putting it behind a paywall, or building a paid application or hosted service around it. I ask you to respect that intention: please keep this work freely available, credit its origins, and direct people to [my official GitHub repository](https://github.com/dkjroot/verwrity) for the software.

If you want to help fund my development, please contribute **directly to me** through [Buy Me a Coffee](https://buymeacoffee.com/dkjroot). Paying a distributor or hosting provider does not fund my work unless I explicitly say otherwise. There is no obligation to contribute.

**This is a personal request, not an additional license restriction.** The legal permissions stated in the [GNU General Public License v3.0](license.txt) remain unchanged by this request. See [licensing details](LICENSING.md) and [third-party credits](THIRD_PARTY_NOTICES.txt).
