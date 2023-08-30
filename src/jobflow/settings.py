"""Settings for jobflow."""

import warnings
from collections import defaultdict
from pathlib import Path

from maggma.stores import MemoryStore
from pydantic import BaseSettings, Field, root_validator

from jobflow import JobStore

DEFAULT_CONFIG_FILE_PATH = Path("~/.jobflow.yaml").expanduser().as_posix()

__all__ = ["JobflowSettings"]


def _default_additional_store():
    """Create a default MemoryStore and connect it.

    This is a private function used for the additional_stores in
    the default JOB_STORE.
    """
    mem_store = MemoryStore()
    mem_store.connect()
    return mem_store


class JobflowSettings(BaseSettings):
    """
    Settings for jobflow.

    The default way to modify these is to modify ~/.jobflow.yaml. Alternatively,
    the environment variable ``JOBFLOW_CONFIG_FILE`` can be set to point to a yaml file
    with jobflow settings.

    Lastly, the variables can be modified directly though environment variables by
    using the "JOBFLOW" prefix. E..g., ``JOBFLOW_JOB_STORE=path/to/jobstore.file``.

    **Allowed JOB_STORE formats**

    If the store is not supplied, a ``MemoryStore`` will be used. Can be specified in
    multiple formats.

    The simplest format is the yaml dumped version of the store, generated using:

    >>> import yaml
    >>> yaml.dump(store.as_dict())

    Alternatively, the store can be specified as the keys docs_store, additional_stores
    and any other keyword arguments supported by the :obj:`JobStore` constructor. The
    docs_store and additional stores are specified by the ``type`` key which must match
    a Maggma ``Store`` subclass, and the remaining keys are passed to the store
    constructor. For example, the following file would  create a :obj:`JobStore` with a
    ``MongoStore`` for docs and a ``GridFSStore`` or ``S3Store`` as an additional store
    for data.

    GridFSStore example:

    .. code-block:: yaml

        docs_store:
          type: MongoStore
          database: jobflow_unittest
          collection_name: outputs
          host: localhost
          port: 27017
        additional_stores:
          data:
            type: GridFSStore
            database: jobflow_unittest
            collection_name: outputs_blobs
            host: localhost
            port: 27017

    S3Store example (Note: the ``key`` field must be set to ``blob_uuid``):

    .. code-block:: yaml

        docs_store:
          type: MongoStore
          database: jobflow_unittest
          collection_name: outputs
          host: localhost
          port: 27017
        additional_stores:
          data:
            type: S3Store
            bucket: output_blobs
            key: blob_uuid
            index:
              type: MongoStore
              database: jobflow_unittest
              collection_name: output_blobs_index
              host: localhost
              port: 27017
              key: blob_uuid


    Lastly, the store can be specified as a file name that points to a file containing
    the credentials in any format supported by :obj:`.JobStore.from_file`.
    """

    CONFIG_FILE: str = Field(
        DEFAULT_CONFIG_FILE_PATH, description="File to load alternative defaults from."
    )

    # general settings
    JOB_STORE: JobStore = Field(
        default_factory=lambda: JobStore(
            MemoryStore(),
            additional_stores=defaultdict(lambda: _default_additional_store()),
        ),
        description="Default JobStore to use when running locally or using FireWorks. "
        "See the :obj:`JobflowSettings` docstring for more details on the "
        "accepted formats.",
    )
    DIRECTORY_FORMAT: str = Field(
        "%Y-%m-%d-%H-%M-%S-%f",
        description="Date stamp format used to create directories",
    )

    class Config:
        """Pydantic config settings."""

        env_prefix = "jobflow_"

    @root_validator(pre=True)
    def load_default_settings(cls, values):
        """
        Load settings from file or environment variables.

        Loads settings from a root file if available and uses that as defaults in
        place of built in defaults.

        This allows setting of the config file path through environment variables.
        """
        from monty.serialization import loadfn

        config_file_path: str = values.get("CONFIG_FILE", DEFAULT_CONFIG_FILE_PATH)
        new_values = {}
        if Path(config_file_path).exists():
            try:
                new_values.update(loadfn(config_file_path))
            # Catching these two error types is required to handle
            # empty and malformed configs
            except (TypeError, ValueError):
                warnings.warn(
                    f"JobFlow config file was located at {config_file_path} "
                    f"but there was a problem while parsing it."
                )

        store = new_values.get("JOB_STORE")
        if isinstance(store, str):
            new_values["JOB_STORE"] = JobStore.from_file(store)
        elif isinstance(store, dict) and store.get("@class") == "JobStore":
            new_values["JOB_STORE"] = JobStore.from_dict(store)
        elif isinstance(store, dict):
            new_values["JOB_STORE"] = JobStore.from_dict_spec(store)

        new_values.update(values)
        return new_values
