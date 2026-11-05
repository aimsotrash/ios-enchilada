#!/usr/bin/env python3
"""Make selected launchd jobs log to the console (SWEET bring-up debugging).

  patch-launchd-plist.py IN.plist OUT.plist [--env KEY=VALUE ...] LABEL [LABEL ...]

IN is /System/Library/xpc/launchd.plist (binary plist, read by launchd when
booted with launchd_unsecure_cache=1). For every job whose Label is given,
stdout/stderr go to /dev/console (mode 0622, writable by the mobile user)
and the environment asks Apple's frameworks to mirror their logs there:
OS_ACTIVITY_DT_MODE=YES copies os_log to stderr (as under Xcode),
CFLOG_FORCE_STDERR=1 does the same for CFLog/NSLog. Uncaught exception
reasons and the frameworks' own error messages then show on screen.

--env adds KEY=VALUE to the environment of the listed jobs, e.g. the fake
Bluetooth controller test (PLAN-ENCHILADA.md §8 step 2, kernel btfake=1):
  --env BT_HCI_TRANSPORT=H4:POSIX:com.apple.uart.bluetooth com.apple.bluetoothd

Every job's _PanicOnCrash key is also renamed (_PanicOnCrasX), so a crashing
daemon does not panic the system during bring-up.
"""
import plistlib, sys

LOG_ENV = {'OS_ACTIVITY_DT_MODE': 'YES', 'CFLOG_FORCE_STDERR': '1'}


def main():
    src, dst, args = sys.argv[1], sys.argv[2], sys.argv[3:]
    env = dict(LOG_ENV)
    while args[:1] == ['--env']:
        key, _, value = args[1].partition('=')
        env[key] = value
        args = args[2:]
    labels = set(args)
    with open(src, 'rb') as f:
        plist = plistlib.load(f)
    found = set()
    jobs = [j for kind in ('LaunchDaemons', 'LaunchAgents') for j in plist.get(kind, {}).values()]
    for job in jobs:
        if '_PanicOnCrash' in job:
            job['_PanicOnCrasX'] = job.pop('_PanicOnCrash')
        label = job.get('Label')
        if label in labels:
            job['StandardOutPath'] = '/dev/console'
            job['StandardErrorPath'] = '/dev/console'
            job.setdefault('EnvironmentVariables', {}).update(env)
            found.add(label)
    missing = labels - found
    if missing:
        sys.exit(f'jobs not found: {", ".join(sorted(missing))}')
    with open(dst, 'wb') as f:
        plistlib.dump(plist, f, fmt=plistlib.FMT_BINARY)
    print(f'{dst}: console logging for {", ".join(sorted(found))}')


if __name__ == '__main__':
    main()
