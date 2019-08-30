import errno
import logging
from pathlib import Path
import shutil
import subprocess

logger = logging.getLogger(__name__)

class KernelConfigChecker():
  def __init__(self, verbose=False, reviewer=None):
    self.reviewer = reviewer
    self.verbose = verbose
    self.kernel_dir = Path()
    if self.reviewer.git_dir:
      self.kernel_dir = Path(self.reviewer.git_dir)
    if not self.kernel_dir.is_dir():
      raise ValueError('{} is not a directory!'.format(self.kernel_dir))

    self.config_cmd = self.kernel_dir.joinpath('chromeos/scripts/kernelconfig')
    self.genconfig_dir = self.kernel_dir.joinpath('CONFIGS')
    if not self.genconfig_dir.is_dir():
      self.genconfig_dir.mkdir()

  def is_config_change(self, patch):
      # Running the kernelconfig script is a little slow, so for now
      # only do it on CLs that have changed the configs.
      return '+++ b/chromeos/config' in patch

  def create_kernel_configs(self):
      cmd = [str(self.config_cmd), 'genconfig']
      logger.debug('Running {}'.format(' '.join(cmd)))

      subprocess.call(cmd, stdout=subprocess.DEVNULL,
                      stderr=subprocess.DEVNULL)

  def move_genconfigs(self, dest):
    logger.debug('Moving configs {}->{}'.format(self.genconfig_dir, dest))

    if not dest.is_dir():
      dest.mkdir()
    for filename in self.genconfig_dir.glob('*.config'):
      shutil.copy(str(filename), str(dest))

  def rmdir_recursive(self, dir):
    logger.debug('Deleting {}'.format(dir))

    shutil.rmtree(dir)

  def checkout_commit(self, remote, ref, commit):
    retry = 4
    for i in range(0, retry):
      try:
        self.reviewer.checkout(remote, ref, commit)
        break

      except:
        if i == retry - 1:
          raise
        continue

  def streamline_hunks(self, patch):
      patch = patch.splitlines() or []
      ret = []
      # The config files are always sorted, so the hunk headers with their
      # line numbers and line counts are not super necessary, and pretty
      # distracting. Minimize things for better readability.
      for line in patch:
        if line.startswith('@@ '):
          pass

        elif line.startswith('diff '):
          pass

        elif line.startswith('--- '):
          pass

        elif line.startswith('+++ '):
            line = line.split()[1]
            if line.startswith('configs_new/'):
                line = line[len('configs_new/'):] + ':'

            ret.append('')
            ret.append(line)

        else:
          ret.append(line)

      return '\n'.join(ret)

  def get_kernel_configs(self, remote, ref):
    # Reset the working directory back to a pristine state.
    self.reviewer.checkout_reset('.')

    # Check out the tree just before the CL, and generate the full
    # kernel configs.
    self.checkout_commit(remote, ref, 'FETCH_HEAD~1')
    self.create_kernel_configs()
    orig_dir = self.kernel_dir.joinpath('configs_orig')
    self.move_genconfigs(orig_dir)

    # Now check out the CL, and generate the full configs.
    self.reviewer.checkout_reset('chromeos/config')
    self.checkout_commit(remote, ref, 'FETCH_HEAD')
    self.create_kernel_configs()
    new_dir = self.kernel_dir.joinpath('configs_new')
    self.move_genconfigs(new_dir)

    # Compare the two configs against each other.
    cmd = ['diff', '-ru0', 'configs_orig', 'configs_new']
    logger.debug('Running {}'.format(' '.join(cmd)))

    proc = subprocess.Popen(cmd, cwd=str(self.kernel_dir), stdout=subprocess.PIPE)
    kconfig_diff = proc.communicate()[0].decode('UTF-8')
    kconfig_diff = self.streamline_hunks(kconfig_diff)

    # Clean up
    self.reviewer.checkout_reset('chromeos/config')
    self.rmdir_recursive(str(orig_dir))
    self.rmdir_recursive(str(new_dir))
    self.rmdir_recursive(str(self.genconfig_dir))
    return kconfig_diff
