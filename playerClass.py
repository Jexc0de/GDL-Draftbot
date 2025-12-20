SeasonPoints = 112
CaptainPoints = 26

class Player:

    @classmethod
    async def create(cls,client,discordId,points=SeasonPoints):
        discordPlayerData = await client.fetch_user(discordId)
        return cls(discordId,discordPlayerData)

    def __init__(self, discordId, discordPlayerData):
        self.discordId = discordId
        self.discordPlayerData = discordPlayerData
        self.points = SeasonPoints
        #draftedPokemon by dex number and string
        self.draftedPokemon = {}
        #all nicknames of the player wherever the bot and player share a guild
        self.nicknames = {}
        self.missedTurns = 0
        self.maxSingleTurnSpend = SeasonPoints
        self.draftMin = 9
        self.captainLimit = 2
        self.captains = {}
        self.captainPoints = 26


    def update_single_turn_spend(self):#Don't ask why its 9 - val - 1 it just works and I don't question it
        self.maxSingleTurnSpend = max(1,self.points-max(0,(9-len(self.draftedPokemon)-1)))

    def pokemon_count(self):
        return len(self.draftedPokemon)
    
    def greater_then_max_spend(self, pokemonCost):
        return (self.points <= 50) and (pokemonCost > self.maxSingleTurnSpend) and (self.pokemon_count() < self.draftMin)
    
    def capped_spending_check(self):
        return self.points <= 50 and self.pokemon_count() < self.draftMin
    
    def missed_turns_remaining(self):
        if (self.missedTurns>0):
            self.missedTurns -= 1
            return True
        return False

    def draft(self,dexNumber,pokemonName,pokemonCost,captain=False):
        if not captain:
            self.draftedPokemon[dexNumber] = pokemonName
            self.points -= pokemonCost
        else:
            self.draftedPokemon[dexNumber] = pokemonName
            self.captains[dexNumber] = pokemonName
            self.captainPoints -= pokemonCost


    def attempt_captain_draft(self,dexNum,pokemonName,pokemonCost):
        self.update_single_turn_spend()
        if pokemonCost > self.captainPoints:
            return 5
        if dexNum in self.draftedPokemon:
            return 2
        if len(self.captains) == self.captainLimit:
            return 6
        self.draft(dexNum,pokemonName,pokemonCost,captain=True)
        if self.missed_turns_remaining():
            return 4
        return 0

    def attempt_draft(self,dexNum,pokemonName,pokemonCost):
        self.update_single_turn_spend()
        if pokemonCost > self.points:
            return 1
        if dexNum in self.draftedPokemon:
            return 2
        if self.greater_then_max_spend(pokemonCost):
            return 3
        self.draft(dexNum,pokemonName,pokemonCost)
        if self.missed_turns_remaining():
            return 4
        return 0 
    #Returns codes based on draft result
    #0)Success!
    #1)unaffordable
    #2)dex clause
    #3)Greater then max single turn spend
    #4)missed a turn and will draft again
    #5)captain unaffordable
    #6)drafted captain limit