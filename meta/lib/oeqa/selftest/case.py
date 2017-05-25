# Copyright (C) 2013-2017 Intel Corporation
# Released under the MIT license (see COPYING.MIT)

import sys
import os
import shutil
import glob
import errno
from unittest.util import safe_repr

import oeqa.utils.ftools as ftools
from oeqa.utils.commands import runCmd, bitbake, get_bb_var, get_test_layer
from oeqa.core.case import OETestCase

class OESelftestTestCase(OETestCase):
    builddir = os.environ.get("BUILDDIR") or ""
    localconf_path = os.path.join(builddir, "conf/local.conf")
    localconf_backup = os.path.join(builddir, "conf/local.bk")
    testinc_path = os.path.join(builddir, "conf/selftest.inc")
    local_bblayers_path = os.path.join(builddir, "conf/bblayers.conf")
    local_bblayers_backup = os.path.join(builddir, "conf/bblayers.bk")
    testinc_bblayers_path = os.path.join(builddir, "conf/bblayers.inc")
    machineinc_path = os.path.join(builddir, "conf/machine.inc")
    testlayer_path = get_test_layer()

    def __init__(self, methodName="runTest"):
        self._extra_tear_down_commands = []
        self._track_for_cleanup = [
            self.testinc_path, self.testinc_bblayers_path,
            self.machineinc_path, self.localconf_backup,
            self.local_bblayers_backup]

        super(OESelftestTestCase, self).__init__(methodName)

    @classmethod
    def setUpClass(cls):
        super(OESelftestTestCase, cls).setUpClass()
        cls.add_include()

    @classmethod
    def tearDownClass(cls):
        cls.remove_include()
        cls.remove_inc_files()
        super(OESelftestTestCase, cls).tearDownClass()

    @classmethod
    def add_include(cls):
        if "#include added by oe-selftest" \
            not in ftools.read_file(os.path.join(cls.builddir, "conf/local.conf")):
                cls.logger.info("Adding: \"include selftest.inc\" in %s" % os.path.join(cls.builddir, "conf/local.conf"))
                ftools.append_file(os.path.join(cls.builddir, "conf/local.conf"), \
                        "\n#include added by oe-selftest\ninclude machine.inc\ninclude selftest.inc")

        if "#include added by oe-selftest" \
            not in ftools.read_file(os.path.join(cls.builddir, "conf/bblayers.conf")):
                cls.logger.info("Adding: \"include bblayers.inc\" in bblayers.conf")
                ftools.append_file(os.path.join(cls.builddir, "conf/bblayers.conf"), \
                        "\n#include added by oe-selftest\ninclude bblayers.inc")

    @classmethod
    def remove_include(cls):
        if "#include added by oe-selftest.py" \
            in ftools.read_file(os.path.join(cls.builddir, "conf/local.conf")):
                cls.logger.info("Removing the include from local.conf")
                ftools.remove_from_file(os.path.join(cls.builddir, "conf/local.conf"), \
                        "\n#include added by oe-selftest.py\ninclude machine.inc\ninclude selftest.inc")

        if "#include added by oe-selftest.py" \
            in ftools.read_file(os.path.join(cls.builddir, "conf/bblayers.conf")):
                cls.logger.info("Removing the include from bblayers.conf")
                ftools.remove_from_file(os.path.join(cls.builddir, "conf/bblayers.conf"), \
                        "\n#include added by oe-selftest.py\ninclude bblayers.inc")

    @classmethod
    def remove_inc_files(cls):
        try:
            os.remove(os.path.join(cls.builddir, "conf/selftest.inc"))
            for root, _, files in os.walk(get_test_layer()):
                for f in files:
                    if f == 'test_recipe.inc':
                        os.remove(os.path.join(root, f))
        except OSError as e:
            pass

        for incl_file in ['conf/bblayers.inc', 'conf/machine.inc']:
            try:
                os.remove(os.path.join(cls.builddir, incl_file))
            except:
                pass

    def setUp(self):
        super(OESelftestTestCase, self).setUp()
        os.chdir(self.builddir)
        # Check if local.conf or bblayers.conf files backup exists
        # from a previous failed test and restore them
        if os.path.isfile(self.localconf_backup) or os.path.isfile(
                self.local_bblayers_backup):
            self.logger.debug("\
Found a local.conf and/or bblayers.conf backup from a previously aborted test.\
Restoring these files now, but tests should be re-executed from a clean environment\
to ensure accurate results.")
            try:
                shutil.copyfile(self.localconf_backup, self.localconf_path)
            except OSError as e:
                if e.errno != errno.ENOENT:
                    raise
            try:
                shutil.copyfile(self.local_bblayers_backup,
                                self.local_bblayers_path)
            except OSError as e:
                if e.errno != errno.ENOENT:
                    raise
        else:
            # backup local.conf and bblayers.conf
            shutil.copyfile(self.localconf_path, self.localconf_backup)
            shutil.copyfile(self.local_bblayers_path, self.local_bblayers_backup)
            self.logger.debug("Creating local.conf and bblayers.conf backups.")
        # we don't know what the previous test left around in config or inc files
        # if it failed so we need a fresh start
        try:
            os.remove(self.testinc_path)
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise
        for root, _, files in os.walk(self.testlayer_path):
            for f in files:
                if f == 'test_recipe.inc':
                    os.remove(os.path.join(root, f))

        for incl_file in [self.testinc_bblayers_path, self.machineinc_path]:
            try:
                os.remove(incl_file)
            except OSError as e:
                if e.errno != errno.ENOENT:
                    raise

        if self.tc.custommachine:
            machine_conf = 'MACHINE ??= "%s"\n' % self.tc.custommachine
            self.set_machine_config(machine_conf)

        # tests might need their own setup
        # but if they overwrite this one they have to call
        # super each time, so let's give them an alternative
        self.setUpLocal()

    def setUpLocal(self):
        pass

    def tearDown(self):
        if self._extra_tear_down_commands:
            failed_extra_commands = []
            for command in self._extra_tear_down_commands:
                result = runCmd(command, ignore_status=True)
                if not result.status ==  0:
                    failed_extra_commands.append(command)
            if failed_extra_commands:
                self.logger.warning("tearDown commands have failed: %s" % ', '.join(map(str, failed_extra_commands)))
                self.logger.debug("Trying to move on.")
            self._extra_tear_down_commands = []

        if self._track_for_cleanup:
            for path in self._track_for_cleanup:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                if os.path.isfile(path):
                    os.remove(path)
            self._track_for_cleanup = []

        self.tearDownLocal()
        super(OESelftestTestCase, self).tearDown()

    def tearDownLocal(self):
        pass

    def add_command_to_tearDown(self, command):
        """Add test specific commands to the tearDown method"""
        self.logger.debug("Adding command '%s' to tearDown for this test." % command)
        self._extra_tear_down_commands.append(command)

    def track_for_cleanup(self, path):
        """Add test specific files or directories to be removed in the tearDown method"""
        self.logger.debug("Adding path '%s' to be cleaned up when test is over" % path)
        self._track_for_cleanup.append(path)

    def write_config(self, data):
        """Write to <builddir>/conf/selftest.inc"""

        self.logger.debug("Writing to: %s\n%s\n" % (self.testinc_path, data))
        ftools.write_file(self.testinc_path, data)

        if self.tc.custommachine and 'MACHINE' in data:
            machine = get_bb_var('MACHINE')
            self.logger.warning('MACHINE overridden: %s' % machine)

    def append_config(self, data):
        """Append to <builddir>/conf/selftest.inc"""
        self.logger.debug("Appending to: %s\n%s\n" % (self.testinc_path, data))
        ftools.append_file(self.testinc_path, data)

        if self.tc.custommachine and 'MACHINE' in data:
            machine = get_bb_var('MACHINE')
            self.logger.warning('MACHINE overridden: %s' % machine)

    def remove_config(self, data):
        """Remove data from <builddir>/conf/selftest.inc"""
        self.logger.debug("Removing from: %s\n%s\n" % (self.testinc_path, data))
        ftools.remove_from_file(self.testinc_path, data)

    def write_recipeinc(self, recipe, data):
        """Write to meta-sefltest/recipes-test/<recipe>/test_recipe.inc"""
        inc_file = os.path.join(self.testlayer_path, 'recipes-test', recipe, 'test_recipe.inc')
        self.logger.debug("Writing to: %s\n%s\n" % (inc_file, data))
        ftools.write_file(inc_file, data)

    def append_recipeinc(self, recipe, data):
        """Append data to meta-sefltest/recipes-test/<recipe>/test_recipe.inc"""
        inc_file = os.path.join(self.testlayer_path, 'recipes-test', recipe, 'test_recipe.inc')
        self.logger.debug("Appending to: %s\n%s\n" % (inc_file, data))
        ftools.append_file(inc_file, data)

    def remove_recipeinc(self, recipe, data):
        """Remove data from meta-sefltest/recipes-test/<recipe>/test_recipe.inc"""
        inc_file = os.path.join(self.testlayer_path, 'recipes-test', recipe, 'test_recipe.inc')
        self.logger.debug("Removing from: %s\n%s\n" % (inc_file, data))
        ftools.remove_from_file(inc_file, data)

    def delete_recipeinc(self, recipe):
        """Delete meta-sefltest/recipes-test/<recipe>/test_recipe.inc file"""
        inc_file = os.path.join(self.testlayer_path, 'recipes-test', recipe, 'test_recipe.inc')
        self.logger.debug("Deleting file: %s" % inc_file)
        try:
            os.remove(inc_file)
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise
    def write_bblayers_config(self, data):
        """Write to <builddir>/conf/bblayers.inc"""
        self.logger.debug("Writing to: %s\n%s\n" % (self.testinc_bblayers_path, data))
        ftools.write_file(self.testinc_bblayers_path, data)

    def append_bblayers_config(self, data):
        """Append to <builddir>/conf/bblayers.inc"""
        self.logger.debug("Appending to: %s\n%s\n" % (self.testinc_bblayers_path, data))
        ftools.append_file(self.testinc_bblayers_path, data)

    def remove_bblayers_config(self, data):
        """Remove data from <builddir>/conf/bblayers.inc"""
        self.logger.debug("Removing from: %s\n%s\n" % (self.testinc_bblayers_path, data))
        ftools.remove_from_file(self.testinc_bblayers_path, data)

    def set_machine_config(self, data):
        """Write to <builddir>/conf/machine.inc"""
        self.logger.debug("Writing to: %s\n%s\n" % (self.machineinc_path, data))
        ftools.write_file(self.machineinc_path, data)

    # check does path exist    
    def assertExists(self, expr, msg=None):
        if not os.path.exists(expr):
            msg = self._formatMessage(msg, "%s does not exist" % safe_repr(expr))
            raise self.failureException(msg)
    
    # check does path not exist 
    def assertNotExists(self, expr, msg=None):
        if os.path.exists(expr):
            msg = self._formatMessage(msg, "%s exists when it should not" % safe_repr(expr))
            raise self.failureException(msg)
