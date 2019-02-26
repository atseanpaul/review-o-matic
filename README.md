# review-o-matic and friends
This projects includes a few scripts to help review and submit gerrit patches.

## troll-o-matic
This script trolls gerrit for BACKPORT/UPSTREAM/FROMGIT prefixed changes and compares the downstream backport with the upstream source. If a difference between upstream and downstream is detected, the script will print the difference between patches for the human reviewer to validate. The script also checks that the required fields are present in the commit message and checks upstream git logs for "Fixes:" references in case the backport has a bug which is already fixed upstream.

In its current form, the script is hardcoded to target the kernel git repository on crosreview.com

#### Usage
```
usage: troll-o-matic.py [-h] [--git-dir GIT_DIR] [--verbose] [--chatty]
                        [--daemon] [--dry-run] [--force-cl FORCE_CL]
                        [--stats-file STATS_FILE]

Troll gerrit reviews

optional arguments:
  -h, --help            show this help message and exit
  --git-dir GIT_DIR     Path to git directory
  --verbose             print commits
  --chatty              print diffs
  --daemon              Run in daemon mode, for continuous trolling
  --dry-run             skip the review step
  --force-cl FORCE_CL   Force review a CL
  --stats-file STATS_FILE
                        Path to stats file


```

#### Example Invocations
Daemon mode:
```
troll-o-matic.py --git-dir ~/s/review_repo/ --daemon --stats-file ~/review_stats/review_stats.json
```

Target a CL for testing:
```
troll-o-matic.py --git-dir ~/s/review_repo/ --force-cl 1487385 --dry-run
```



## submit-o-matic
This script monitors a set of patches on gerrit, flipping the CodeReview/Verify/CQReady bits on the review until it is merged.

#### Usage
```
usage: submit-o-matic.py [-h] --last_cid LAST_CID [--daemon] [--no-review]
                         [--no-verify] [--no-ready]

Auto review/submit gerrit cls

optional arguments:
  -h, --help           show this help message and exit
  --last_cid LAST_CID  Gerrit change-id of last patch in set
  --daemon             Run in daemon mode, continuously update changes until
                       merged
  --no-review          Don't mark changes as reviewed
  --no-verify          Don't mark changes as verified
  --no-ready           Don't mark changes as ready
```

#### Example Invocations
Flip the Verify and CQReady bits on the entire gerrit series ending in change 1439600. Continue to flip those bits until it has been marked as merged.
```
submit-o-matic.py --last_cid 1439600 --daemon --no-review
```



## backport-o-matic
Adds the required fields to a backport commit message. Should be used in conjunction with git filter-branch to alter a series of git commits.

#### Usage
```
usage: backport-o-matic.py [-h] [--prefix PREFIX] [--tree TREE] [--bug BUG]
                           [--test TEST] [--sob SOB] [--no-preserve-tags]

    Add CrOS goo to commit range
 
    Usage:
      git filter-branch --msg-filter "backport-o-matic.py --prefix='UPSTREAM'         --bug='b:12345' --test='by hand' --sob='Real Name <email>'"
  

optional arguments:
  -h, --help          show this help message and exit
  --prefix PREFIX     subject prefix
  --tree TREE         location of git-tree
  --bug BUG           BUG= value
  --test TEST         TEST= value
  --sob SOB           "Name <email>" for SoB
  --no-preserve-tags  Overwrite existing CrOS tags
```

#### Example Invocations
```
git filter-branch -f --msg-filter "backport-o-matic.py --prefix='FROMGIT' --bug='None' --test='Tested, trust me' --sob='Sean Paul <seanpaul@chromium.org>' --tree='git://anongit.freedesktop.org/drm/drm'" 031ae70a3329..
```


## review-o-matic

Does what troll-o-matic does above, but for your local git tree instead of gerrit.

#### Usage
```
usage: review-o-matic.py [-h] --start START [--prefix PREFIX] [--verbose]
                         [--chatty]

Auto review UPSTREAM patches

optional arguments:
  -h, --help       show this help message and exit
  --start START    commit hash to start from
  --prefix PREFIX  subject prefix
  --verbose        print commits
  --chatty         print diffs
```

#### Example Invocations
```
review-o-matic.py --start "$( git log --pretty=format:%H cros/chromeos-4.19.. | tail -n1 )"
```
