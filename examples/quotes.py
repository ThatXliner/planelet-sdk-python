import random

from superplane import (
    ActionContext,
    Param,
    ParamOption,
    create_planelet,
)

planelet = create_planelet(
    id="quotes",
    label="Random Quotes",
    icon="quote",
    description="Get random quotes and generate greetings",
)

QUOTES = [
    {"text": "The only way to do great work is to love what you do.", "author": "Steve Jobs"},
    {"text": "Innovation distinguishes between a leader and a follower.", "author": "Steve Jobs"},
    {"text": "Stay hungry, stay foolish.", "author": "Steve Jobs"},
    {"text": "Move fast and break things.", "author": "Mark Zuckerberg"},
    {"text": "The best way to predict the future is to invent it.", "author": "Alan Kay"},
    {"text": "Talk is cheap. Show me the code.", "author": "Linus Torvalds"},
]


@planelet.action(
    "get-quote",
    label="Get Random Quote",
    description="Returns a random inspirational quote",
    parameters={
        "category": Param(
            label="Category",
            type="select",
            description="Filter quotes by category",
            options=[
                ParamOption(label="All", value="all"),
                ParamOption(label="Innovation", value="innovation"),
                ParamOption(label="Motivation", value="motivation"),
            ],
        ),
    },
)
async def get_quote(ctx: ActionContext) -> dict:
    quote = random.choice(QUOTES)
    return {"quote": quote["text"], "author": quote["author"]}


@planelet.action(
    "greet",
    label="Generate Greeting",
    description="Generate a personalized greeting message",
    parameters={
        "name": Param(
            label="Name",
            type="string",
            description="Name of the person to greet",
            required=True,
        ),
        "style": Param(
            label="Style",
            type="select",
            description="Greeting style",
            required=True,
            options=[
                ParamOption(label="Formal", value="formal"),
                ParamOption(label="Casual", value="casual"),
                ParamOption(label="Enthusiastic", value="enthusiastic"),
            ],
        ),
    },
)
async def greet(ctx: ActionContext) -> dict:
    name = ctx.parameters["name"]
    style = ctx.parameters.get("style", "casual")

    greetings = {
        "formal": f"Good day, {name}. It is a pleasure to make your acquaintance.",
        "casual": f"Hey {name}, what's up?",
        "enthusiastic": f"OMG {name}!!! SO GREAT to see you!",
    }

    return {
        "greeting": greetings.get(style, greetings["casual"]),
        "style": style,
        "recipient": name,
    }


planelet.listen(3001)
