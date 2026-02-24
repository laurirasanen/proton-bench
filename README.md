# vkd3d-bench

## Dependencies

- python3
- gamescope compiled with `-D input_emulation=enabled`

## Usage

Install python dependencies:

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Update libei bindings:

```sh
python libei/proto/ei-scanner \
    --component ei \
    --output util/libei_bindings.py \
    libei/proto/protocol.xml \
    libei/test/eiproto.py.tmpl
```

Run benchmarks: 

```sh
python bench.py
```
