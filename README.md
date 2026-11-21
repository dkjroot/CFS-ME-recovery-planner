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

Start with the suggestions for today. Add quiet rest, everyday tasks or
anything else that fits your day to your routine. You can give each item
its own planned minutes and log what you actually did. If you want a
graph for one activity, choose it under **Plan settings** and set its
usual and step-back limits.

The roadmap starts with making days steadier, then reviewing one change
and making room for things you want to return to. It shows the earliest
dates to review those stages. The default review window is seven usual
or better check-ins. You can change that under **Review timing**. A low
or crash starts the count again and brings the step-back suggestions
forward for at least two later check-ins. After a day above plan, the planner waits for the next few days
of check-ins before offering a stage change.

The dates are for reviewing your plans. You decide when to change them.
The roadmap draws on energy management principles such as planning rest,
taking account of different kinds of activity and adjusting to changes
in symptoms. [NICE guidance on energy management](https://www.nice.org.uk/guidance/ng206/chapter/Recommendations#energy-management)

The graph shows your logged minutes and the plan you’ve saved. Once
there are enough check-ins, it also shows what the next week would look
like at your typical recent level. After a low or crash, you can review
the three days beforehand, including any extra routine items you logged.
The activity log also shows what was recorded in the three days after
an activity. If you switch to your lower limit, it
stays there until you choose to return to your usual plan.

Plans and check-ins are saved as separate JSON files on the computer
running the planner. The `local_data` folder also contains a small SQLite
database with accounts, password hashes and sign-in sessions. The planner
files are readable by anyone with access to that folder on the host.

### Free to use. Please help keep it that way.

I develop this project to be freely available to everyone, supported, if at all, by voluntary contributions. I do not want other people to profit from my work by selling copies, putting it behind a paywall, or building a paid application or hosted service around it. I ask you to respect that intention: please keep this work freely available, credit its origins, and direct people to [my official GitHub repository](https://github.com/dkjroot/verwrity) for the software.

If you want to help fund my development, please contribute **directly to me** through [Buy Me a Coffee](https://buymeacoffee.com/dkjroot). Paying a distributor or hosting provider does not fund my work unless I explicitly say otherwise. There is no obligation to contribute.

**This is a personal request, not an additional license restriction.** The legal permissions stated in the [GNU General Public License v3.0](license.txt) remain unchanged by this request. See [licensing details](LICENSING.md) and [third-party credits](THIRD_PARTY_NOTICES.txt).
