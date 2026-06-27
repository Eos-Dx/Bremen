# EOS Product Bundle

Purpose:

```text
install XRD-preprocessing
install Aramis
install container
create empty Bremen folder
copy bundled H5 data
create/update conda env eosproduct
install Miniforge automatically if conda is missing
install container, XRD-preprocessing, and Aramis as editable local packages
run tests
launch Aramis marimo notebooks
```

Run:

```bash
tar -xzf eosproduct_onboarding_bundle.tar.gz
cd eosproduct_onboarding_bundle
./install.sh
```

The installer asks before running tests or launching notebooks. If tests are
accepted, XRD-preprocessing and Aramis tests run together in a separate Terminal
window. If notebooks are accepted, Aramis one-to-one and one-to-many notebooks
open in separate Terminal windows.

If git clone/update succeeds, installer uses latest pushed repositories. If git
is unavailable or clone fails, installer uses the bundled repository fallback.

If `conda` is not installed, the installer asks to install Miniforge into:

```text
~/miniforge3
```

Default target:

```text
~/dev/eosproduct
```

Manual test commands:

```bash
./run_tests.sh ~/dev/eosproduct xrd
./run_tests.sh ~/dev/eosproduct aramis
./run_tests.sh ~/dev/eosproduct all
```

Manual notebook command:

```bash
./run_aramis_notebooks.sh ~/dev/eosproduct
```

Notebook behavior:

```text
default settings run automatically
changed settings are frozen until Validate settings is clicked
one-to-one and one-to-many open in separate Terminal windows
```

Data:

```text
data/combined_archive.h5
notebooks use this path automatically after bundle install
```

Build full-data bundle:

```bash
DATA_H5=/path/to/combined_archive.h5 ./make_bundle.sh
```
