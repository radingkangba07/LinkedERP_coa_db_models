"""Read side of erp-schema-graph, copied so the loader has no dependency on that private repository.

Source: github.com/bhavna-linkedrp/erp_schema_graph, commit e6ca536 (package 0.2.0, graph contract 2.0.0).
contract.py, diagnostics.py and tables.py are verbatim copies; snapshot.py keeps only the read and verify
functions. When the producer changes the CSV format, copy the new files here in the same change: until then
read_tables() rejects the new snapshots because their headers no longer match.
"""

CONTRACT_VERSION = "2.0.0"
SOURCE_COMMIT = "e6ca536c61ee0b73e4f9cb8d148bbec778116e87"
__version__ = "0.2.0"
