import json, os
from divisionClass import Division
from playerClass import Player

class encodeDB(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, 'toJSON'):
            return obj.toJSON()
        else:
            return json.JSONEncoder.default(self, obj)

class SaveManager():

    def __init__(self, fileName):
        self.fileName = fileName
    
    def checkJson(self):
        return os.path.getsize(self.fileName)

    # Most of these are unused. Mainly put here if we wanted to autosave after certain commands are executed
    def saveDivision(self, division):
        with open(self.fileName, "r+", encoding="utf-8") as f:
            jdata = json.load(f)

            jdata[division.name] = division
            f.seek(0)
            json.dump(jdata, self.jsonFile, indent=4, cls=encodeDB)
            f.truncate()
    
    def saveDivisionAttr(self, division_name, attr_name, attr, encoder=None):
        with open(self.fileName, "r+", encoding="utf-8") as f:
            jdata = json.load(f)

            jdata[division_name][attr_name] = attr
            f.seek(0)
            json.dump(jdata, f, indent=4, cls=encodeDB)
            f.truncate()
            
    def savePlayer(self, division_name, player, player_index):
        with open(self.fileName, "r+", encoding="utf-8") as f:
            jdata = json.load(f)
            
            jdata[division_name]["players"][player_index] = player
            f.seek(0)
            json.dump(jdata, f, indent=4, cls=encodeDB)
            f.truncate()
    
    def savePlayerAttr(self, division_name, player_index, attr_name, attr, encoder=None):
        with open(self.fileName, "r+", encoding="utf-8") as f:
            jdata = json.load(f)

            jdata[division_name]["players"][player_index][attr_name] = attr
            f.seek(0)
            json.dump(jdata, f, indent=4, cls=encodeDB)
            f.truncate()

    def saveAll(self, divisions):
        with open(self.fileName, 'r+', encoding='utf-8') as f:
            f.seek(0)
            json.dump(divisions, f, indent=4, cls=encodeDB)
            f.truncate()

    #Kill me
    #Could be made into a JSONDecoder class, but I don't know how I would hanlde the async part. This works though even if it feels.... bad
    async def load(self, bot):
        with open(self.fileName, 'r', encoding='utf-8') as f:
            jdata = json.load(f)
            divisionDict = {}
            for division_name, division in jdata.items():
                jdiv = Division(division_name, bot)
                jdiv.draftChannel = bot.get_channel(division["draftChannel"])
                activeTurn = None
                #decodes the players
                for players in division["players"]:
                    p = await Player.create(bot, players["discordId"], points=players["points"])
                    p.draftedPokemon = {int(dex): pokemon for dex, pokemon in players["draftedPokemon"].items()}
                    p.nicknames = players["nicknames"]
                    p.missedTurns = players["missedTurns"]
                    p.maxSingleTurnSpend = players["maxSingleTurnSpend"]
                    p.captains = players["captains"]
                    p.captainPoints = players["captainPoints"]
                    p.waitingOnConfirmation = players["waitingOnConfirmation"]
                    jdiv.players.append(p)
                    if not activeTurn and p.discordId == division["activeTurn"]:
                        jdiv.activeTurn = p
                
                jdiv.turnTracker = division["turnTracker"]
                jdiv.forward = division["forward"]
                jdiv.remainingTime = division["remainingTime"]
                jdiv.draftedPokemon = division["draftedPokemon"]
                jdiv.complexBans = division["complexBans"]
                jdiv.roundCounter = division["roundCounter"]
                jdiv.savedMessageId = division["savedMessageId"]
                jdiv.savedDraftRequest = division["savedDraftRequest"]
                jdiv.confirmMessageId = division["confirmMessageId"]

                divisionDict[division_name] = jdiv

            return divisionDict

