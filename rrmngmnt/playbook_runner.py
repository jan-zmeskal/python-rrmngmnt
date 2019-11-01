import contextlib
import json
import os.path
import uuid

from rrmngmnt.resource import Resource
from rrmngmnt.service import Service


# TODO: Add debug messages

class PlaybookRunner(Service):

    class PlaybookAdapter(Resource.LoggerAdapter):
        def process(self, msg, kwargs):
            return (
                "[%s] %s" % (
                    self.extra['self'].short_run_uuid,
                    msg
                ),
                kwargs
            )

    tmp_dir = "/tmp"
    binary = "ansible-playbook"
    extra_vars_file = "extra_vars.json"
    default_inventory_name = "inventory"
    default_inventory_content = "localhost ansible_connection=local"
    check_mode_param = "--check"

    def __init__(self, host):
        super(PlaybookRunner, self).__init__(host)
        self.run_uuid = uuid.uuid4()
        self.short_run_uuid = str(self.run_uuid).split('-')[0]
        self.tmp_exec_dir = None
        self.cmd = [self.binary]
        self.rc = None
        self.out = None
        self.err = None

    @contextlib.contextmanager
    def _exec_dir(self):
        # In temporary location, create a directory whose name is same
        # as the short run UUID
        exec_dir_path = os.path.join(self.tmp_dir, self.short_run_uuid)
        self.host.fs.rmdir(exec_dir_path)
        self.host.fs.mkdir(exec_dir_path)
        self.tmp_exec_dir = exec_dir_path
        try:
            yield
        finally:
            self.tmp_exec_dir = None
            self.host.fs.rmdir(exec_dir_path)

    def _upload_file(self, file_):
        file_path_on_host = os.path.join(
            self.tmp_exec_dir, os.path.basename(file_)
        )
        self.host.fs.put(path_src=file_, path_dst=file_path_on_host)
        return file_path_on_host

    def _dump_vars_to_json(self, vars_):
        file_path_on_host = os.path.join(
            self.tmp_exec_dir, self.extra_vars_file
        )
        self.host.fs.create_file(
            content=json.dumps(vars_), path=file_path_on_host
        )
        return file_path_on_host

    def _generate_default_inventory(self):
        file_path_on_host = os.path.join(
            self.tmp_exec_dir, self.default_inventory_name
        )
        self.host.fs.create_file(
            content=self.default_inventory_content,
            path=file_path_on_host
        )
        return file_path_on_host

    def run(
        self, playbook, extra_vars=None, vars_files=None, inventory=None,
        verbose_level=1, run_in_check_mode=False, playbook_logger=None
    ):
        """
        Run Ansible playbook on host

        Args:
            playbook (str): Path to playbook you want to execute
            extra_vars (dict): Dictionary of extra variables that are to be
                passed to playbook execution. They will be dumped into JSON
                file and included using -e@ parameter
            vars_files (list): List of additional variable files to be included
                using -e@ parameter. Variables specified in those files will
                override those specified in extra_vars param
            inventory (str): Path to an inventory file to be used for playbook
                execution. If none is provided, default inventory including
                only localhost will be generated and used
            verbose_level (int): How much should playbook be verbose. Possible
                values are 1 through 5 with 1 being the most quiet and 5 being
                the most verbose
            run_in_check_mode (bool): If True, playbook will not actually be
                executed, but instead run with --check parameter
            playbook_logger (logging.Logger): If you want to redirect output of
                Ansible playbook to an alternate location, you can provide
                instance of logging.Logger here. Your logger will be modified
                by PlaybookAdapter which makes sure that each line of Ansible
                output is matched with short run ID. If no logger is provided
                here, RemoteExecutor logger will be used

        Returns:
            tuple: tuple of (rc, out, err)
        """
        with self._exec_dir():

            if extra_vars:
                self.cmd.append(
                    "-e@{}".format(self._dump_vars_to_json(extra_vars))
                )

            if vars_files:
                for f in vars_files:
                    self.cmd.append("-e@{}".format(f))

            self.cmd.append("-i")
            if inventory:
                self.cmd.append(self._upload_file(inventory))
            else:
                self.cmd.append(self._generate_default_inventory())

            self.cmd.append("-{}".format("v" * verbose_level))

            if run_in_check_mode:
                self.cmd.append(self.check_mode_param)

            self.cmd.append(self._upload_file(playbook))

            self.logger.info(
                "Executing: {}. Playbook run ID: {}".format(
                    " ".join(self.cmd), self.short_run_uuid
                )
            )
            if playbook_logger:
                playbook_logger = self.PlaybookAdapter(
                    playbook_logger,
                    {'self': self}
                )
            self.rc, self.out, self.err = self.host.executor(
                real_time_log=True,
                logger=playbook_logger
            ).run_cmd(self.cmd)

            self.logger.info(
                "Ansible playbook run with ID {} finished with RC: {}".format(
                    self.short_run_uuid, self.rc
                )
            )

        return self.rc, self.out, self.err
