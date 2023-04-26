import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel

from src.event.base import EventsManager

from ..agent.base import Agent
from ..location.base import Location
from ..utils.database.database import supabase
from .context import WorldContext, WorldData


class World(BaseModel):
    id: UUID
    name: str
    locations: list[Location]
    agents: list[Agent]
    context: WorldContext

    def __init__(self, name: str, current_step: int = 0, id: Optional[UUID] = None):
        if id is None:
            id = uuid4()

        # get all locations
        (_, locations), count = (
            supabase.table("Locations").select("*").eq("world_id", id).execute()
        )

        # get all agents
        (_, agents), count = (
            supabase.table("Agents").select("*").eq("world_id", id).execute()
        )

        context = WorldContext(
            world=WorldData(id=id, name=name, current_step=current_step),
            agents=agents,
            locations=locations,
        )

        locations = [Location(**location) for location in locations]
        agents = [
            Agent.from_db_dict(agent_dict, locations, context=context)
            for agent_dict in agents
        ]

        super().__init__(
            id=id,
            name=name,
            locations=locations,
            agents=agents,
            context=context,
        )

    @classmethod
    def from_id(cls, id: UUID):
        data, count = supabase.table("Worlds").select("*").eq("id", str(id)).execute()
        return cls(**data[1][0])

    @classmethod
    def from_name(cls, name: str):
        (_, worlds), count = (
            supabase.table("Worlds").select("*").eq("name", name).execute()
        )

        if not worlds:
            raise ValueError(f"World with name {name} not found")

        return cls(**worlds[0])

    def run_step(self):
        # Refresh events for this step
        self.context.events_manager.refresh_events(self.context.world.current_step)

        # Run agents
        for agent in self.agents:
            agent.run_for_one_step()

        # Increment step
        self.context.update_step(self.context.world.current_step + 1)
        supabase.table("Worlds").update(
            {"current_step": self.context.world.current_step}
        ).eq("id", str(self.id)).execute()

    def run(self, steps: int = 1):
        for _ in range(steps):
            self.run_step()


def get_worlds():
    data, count = supabase.table("Worlds").select("*").execute()
    return [World(**world) for world in data[1]]
