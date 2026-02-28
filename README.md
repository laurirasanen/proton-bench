# proton-bench

Experimental benchmark automation for proton.

![graph](./graphs/wukong-2026-02-26.png)

## Benchmarks

Currently supported titles:

- Black Myth: Wukong Benchmark Tool (3132990)
- Baldurs Gate 3 (1086940)

## Dependencies

- python3
- gamescope compiled with `-D input_emulation=enabled`
- mangoapp
- proton, assumed to be at `../proton`

## Usage

Install python dependencies:

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run benchmarks: 

```sh
python bench.py
```

For individual bench dependencies, see top of the source file in ./benchmarks.

Create a graph:

```sh
python graph.py
```

Updating libei bindings:

```sh
python libei/proto/ei-scanner \
    --component ei \
    --output util/libei_bindings.py \
    libei/proto/protocol.xml \
    libei/test/eiproto.py.tmpl
```
