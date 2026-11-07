def route_research(state):
    return "research" if state.get("targets") else "no_targets"
