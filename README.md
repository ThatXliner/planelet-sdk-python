# SuperPlane Planelet SDK for Python

Build custom SuperPlane integrations in Python. Define actions and webhook triggers with decorators, and the SDK serves the full Planelet protocol over HTTP.

## Quick Start

### 1. Create a new project

```bash
mkdir my-planelet && cd my-planelet
python -m venv .venv && source .venv/bin/activate
pip install superplane-planelet-sdk
```

### 2. Write your Planelet

```python
# main.py
from superplane import create_planelet, Param, ActionContext

planelet = create_planelet(
    id="my-planelet",
    label="My Planelet",
    description="Does useful things",
)

@planelet.action(
    "hello",
    label="Say Hello",
    description="Generates a greeting",
    parameters={
        "name": Param(label="Name", type="string", required=True),
    },
)
async def hello(ctx: ActionContext):
    return {"message": f"Hello, {ctx.parameters['name']}!"}

planelet.listen(3001)
```

### 3. Run it

```bash
python main.py
# Uvicorn running on http://0.0.0.0:3001
```

### 4. Connect to SuperPlane

1. In SuperPlane, add a new **Planelets** integration
2. Set **Server URL** to your Planelet server's address
3. Optionally set an **Auth Token**
4. Save — SuperPlane fetches your manifest and the integration goes ready

## Documentation

See [PLANELET-DOCS.md](PLANELET-DOCS.md) for the full SDK reference, trigger/webhook guide, and protocol details.

## Example

See [`examples/quotes.py`](examples/quotes.py) for a complete example with two actions. Run it:

```bash
cd examples
python quotes.py
```

Then connect SuperPlane to `http://localhost:3001`.
