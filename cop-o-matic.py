#!/usr/bin/python3

import argparse
import logging
import subprocess
import sys

from reviewer import Reviewer
from trollconfig import TrollConfig
from trollreviewer import ChangeReviewer
from trollreviewerfromgit import FromgitChangeReviewer
from trollreviewerupstream import UpstreamChangeReviewer
from trollreviewerfromlist import FromlistChangeReviewer
from trollreviewerchromium import ChromiumChangeReviewer

logging.basicConfig(stream=sys.stdout, level=logging.WARNING)


class CurrentRevision:
    def __init__(self, commit_message, name, email):
        self.commit_message = commit_message
        self.uploader_name = name
        self.uploader_email = email


class Change:
    def __init__(self, hash, subject, commit_message, patch, name, email):
        self.subject = subject
        self.patch = patch
        self.current_revision = CurrentRevision(commit_message, name, email)
        self.url = lambda: hash


def do_review(project, change, verbose):
    c = change
    rev = Reviewer(verbose=verbose)
    age_days = None
    dry_run = False

    if not ChangeReviewer.can_review_change(project, c, age_days):
        print("Cannot review")
        return 0

    gerrit_msg_limit = 16384
    reviewer = None
    if FromlistChangeReviewer.can_review_change(project, c, age_days):
        reviewer = FromlistChangeReviewer(project, rev, c, gerrit_msg_limit, dry_run)
    elif FromgitChangeReviewer.can_review_change(project, c, age_days):
        reviewer = FromgitChangeReviewer(
            project, rev, c, gerrit_msg_limit, dry_run, age_days
        )
    elif UpstreamChangeReviewer.can_review_change(project, c, age_days):
        reviewer = UpstreamChangeReviewer(project, rev, c, gerrit_msg_limit, dry_run)
    elif ChromiumChangeReviewer.can_review_change(project, c, age_days):
        reviewer = ChromiumChangeReviewer(
            project, rev, c, gerrit_msg_limit, dry_run, verbose
        )
    else:
        print("Reviewer not found")
        return 0

    reviewer.gerrit_patch = c.patch
    reviewer.change = c
    review = reviewer.review_patch()
    print(review.generate_review_message(None))

    return 0 if review.vote >= 0 else 42


def get_change(ref):
    sha1 = (
        subprocess.check_output(["git", "log", "--format=%H", "-1", ref])
        .decode("utf-8")
        .strip()
    )
    subject = (
        subprocess.check_output(["git", "log", "--format=%s", "-1", ref])
        .decode("utf-8")
        .strip()
    )
    commit_message = (
        subprocess.check_output(["git", "log", "--format=%b", "-1", ref])
        .decode("utf-8")
        .strip()
    )
    patch = subprocess.check_output(["git", "show", ref]).decode("utf-8").strip()
    name = (
        subprocess.check_output(["git", "log", "--format=%cn", "-1", ref])
        .decode("utf-8")
        .strip()
    )
    email = (
        subprocess.check_output(["git", "log", "--format=%ce", "-1", ref])
        .decode("utf-8")
        .strip()
    )
    return Change(sha1, subject, commit_message, patch, name, email)


def main():
    parser = argparse.ArgumentParser(description="ChromeOS tags reviewer")
    parser.add_argument("--verbose", help="print commits", action="store_true")
    parser.add_argument("--ref", help="git ref", required=True)
    parser.add_argument("--project", help="Path to config file", required=True)
    parser.add_argument("--config", help="Project to run", required=True)
    args = parser.parse_args()

    logger = logging.getLogger("rom")
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.WARNING)

    config = TrollConfig(args.config)
    project = config.get_project(args.project)

    change = get_change(args.ref)

    return do_review(project, change, args.verbose)


if __name__ == "__main__":
    sys.exit(main())
