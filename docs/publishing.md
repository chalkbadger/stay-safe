# Publish the package

The next package version is 0.2.3. Publication is pending: the owner must establish
PyPI ownership of `stay-safe` and supply a scoped publishing credential. Do not
remove the README's pending notice until the public command below has run.

From a clean checkout of the accepted release commit, in a development environment:

```sh
python3 -m pip install build "setuptools>=77" wheel
python3 check_tests.py
python3 -m build
uv publish dist/stay_safe-0.2.3*
```

Use PyPI's credential prompt or its supported environment configuration; never
commit a token. Build tools are development dependencies; the diagnostic has no
runtime dependencies. The build rejects a dirty checkout or an archive without a
full source revision. It bundles the reference files and source revision in both
distribution formats. Do not reuse a version already uploaded to PyPI.

The explicit Python option matters: uv 0.13.8 on a Mac whose only PATH Python
was 3.9.6 rejected the package without it instead of selecting a newer interpreter.

In a new directory, retrieve the public release (without local wheel options):

```sh
uvx --python 3.11 stay-safe@0.2.3 --help
uvx --python 3.11 stay-safe@0.2.3 --save
```

Record the version, source commit, platform, selected Python, output and exit
status. Review the saved page and source links. For a reproducible diagnostic,
select a non-private fixture using `--config FILE`; incomplete inspection exits 2.
Once that succeeds, replace the README's pending paragraph with the verified
pinned command. Keep the clone and ZIP routes.
