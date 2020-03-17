import argparse
import collections
import configparser
import logging
import pathlib

logger = logging.getLogger('rom.troll.config')

TrollConfigProject = collections.namedtuple('TrollConfigProject',
                                            [
                                              'name',
                                              'gerrit_project',
                                              'mainline_repo',
                                              'mainline_branch',
                                              'local_repo',
                                              'gerrit_remote_name',
                                              'review_kconfig',
                                              'prefixes',
                                              'patchworks',
                                              'blacklist'
                                            ])

TrollConfigPatchwork = collections.namedtuple('TrollConfigPatchwork',
                                              [
                                                'name',
                                                'host',
                                                'path',
                                                'has_comments'
                                              ])

class TrollConfig(object):
  def __init__(self):
    self.parse_cmdline()

    if self.force_all:
      self.dry_run = True

    self.config = configparser.ConfigParser()
    self.config.read(self.config_file)

    self.parse_globals()
    self.parse_projects()

  def parse_globals(self):
    self.gerrit_url = self.config.get('global', 'GerritUrl')
    self.stats_file = self.config.get('global', 'StatsFile', fallback=None)
    self.results_file = self.config.get('global', 'ResultsFile', fallback=None)
    self.log_file = self.config.get('global', 'LogFile', fallback=None)
    self.project_names = self.config.get('global', 'Projects').split(',')

  def parse_projects(self):
    self.projects = {}
    for p in self.config.get('global', 'Projects').split(','):
      self.projects[p] = self.build_project('project_{}'.format(p))

  def build_project(self, sec):
    if self.force_prefix:
      prefixes = [self.force_prefix]
    else:
      prefixes = self.config.get(sec, 'Prefixes').split(',')

    patchworks = []
    for p in self.config.get(sec, 'ApprovedPatchworks', fallback='').split(','):
      if not p:
        continue
      patchworks.append(self.build_patchwork('patchwork_{}'.format(p)))

    blacklist = []
    for b in self.config.get(sec, 'BlacklistedRepos', fallback='').split(','):
      if not b:
        continue
      blacklist.append(self.config.get('blacklist_{}'.format(b), 'Regex'))

    return TrollConfigProject(self.config.get(sec, 'Name'),
                              self.config.get(sec, 'GerritProject'),
                              self.config.get(sec, 'MainlineLocation'),
                              self.config.get(sec, 'MainlineBranch'),
                              self.config.get(sec, 'LocalLocation'),
                              self.config.get(sec, 'GerritRemoteName'),
                              self.config.getboolean(sec, 'ReviewKconfig',
                                                     fallback=False),
                              prefixes, patchworks, blacklist)

  def build_patchwork(self, sec):
    return TrollConfigPatchwork(self.config.get(sec, 'Name'),
                                self.config.get(sec, 'Host'),
                                self.config.get(sec, 'Path', fallback=''),
                                self.config.getboolean(sec, 'HasComments'))

  def parse_cmdline(self):
    parser = argparse.ArgumentParser(description='Troll gerrit reviews')
    parser.add_argument('--verbose', help='print commits', action='store_true')
    parser.add_argument('--chatty', help='print diffs', action='store_true')
    parser.add_argument('--daemon', action='store_true',
      help='Run in daemon mode, for continuous trolling')
    parser.add_argument('--dry-run', action='store_true', default=False,
                        help='skip the review step')
    parser.add_argument('--force-cl', default=None, help='Force review a CL')
    parser.add_argument('--force-rev', default=None,
                        help=('Specify a specific revision of the force-cl to '
                             'review (ignored if force-cl is not true)'))
    parser.add_argument('--force-all', action='store_true', default=False,
                        help='Force review all (implies dry-run)')
    parser.add_argument('--force-prefix', default=None,
                        help='Only search for the provided prefix')
    parser.add_argument('--force-project', default=None,
                        help='Only search for changes in the provided project')
    parser.add_argument('--config', default=None, help='Path to config file')

    args = parser.parse_args()
    self.verbose = args.verbose
    self.chatty = args.chatty
    self.daemon = args.daemon
    self.dry_run = args.dry_run
    self.force_cl = args.force_cl
    self.force_rev = args.force_rev
    self.force_all = args.force_all
    self.force_prefix = args.force_prefix
    self.force_project = args.force_project
    self.config_file = args.config

  def get_project(self, project):
    for p in self.projects.values():
      if p.gerrit_project == project:
        return p
    return None
