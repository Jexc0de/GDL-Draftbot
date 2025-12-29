import discord,re,asyncio,csv,difflib,datetime,os
from dotenv import load_dotenv
from discord.utils import get
from playerClass import Player
from divisionClass import Division
from saveManager import SaveManager

#Need a SaveManager timer
#When it times out, pause everything else, save the data, and print "Saving...."

class MyClient(discord.Client):

    #hardcoded division prelist, filled with discord IDs of players in order
    #IronBundlePrelist = [262053075693469696,486970959652323369,612444843616239629,332739281212669952,686025575944421396,147367975291322369,
    # 702544770299330591,140072517581799424,732688360178712596,603351664241672202]
    
    #DelibirdPreList = [778339285941092362,439041234540167179,756503807340445737,416292418586148864,1249603080555724851,433365540082417664,
    # 466631621626560512,716763699984990258,750519011200204822,1450666082166636710]

    DelibirdPreList = [603351664241672202,1247730986238873705,262053075693469696,416292418586148864,778339285941092362,435154768546234368]

    #harcoded admin IDs
    admins = [603351664241672202,1247730986238873705,435154768546234368]
    annoucements_channel = None
    draftMin = 9
    draftMax = 12
    turnDuration = 21600


    def __init__(self, **options):
        super().__init__(**options) 
        self.pokemon_dict = {}
        self.saveManager = SaveManager("saved_data.json")
        with open("pokemonlist_mega_swapped.txt", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            for name, dex_num, points in reader:
                self.pokemon_dict[name.lower()] = {
                    "dex": int(dex_num),
                    "points": int(points)
                }
        
    def get_pokemon_info(self, name: str):
        key = name.lower()
        if key in self.pokemon_dict:
            data = self.pokemon_dict[key]
            return {
                "name": name,
                "dex": data["dex"],
                "points": data["points"]
            }
        return None

    async def on_ready(self):
        print(f"Logged on as {self.user}!")
        target_channel = "announcements"
        for guild in self.guilds:
            for channel in guild.text_channels:
                if target_channel in channel.name:
                    self.announcements_channel = client.get_channel(channel.id)
                    print(f"announcements found:{channel.name}")
                    break

        self.divisions ={
                #"iron-bundle":Division("iron-bundle",self),
                #"delibird": Division("delibird",self)
                "porygon":Division("porygon",self)
            }

        for divison_name, divison in self.divisions.items():
            if divison_name == "iron-bundle":
                prelist = self.IronBundlePrelist
            else:
                prelist = self.DelibirdPreList
            for playerId in prelist:
                current = await Player.create(self,playerId)
                for guild in current.discordPlayerData.mutual_guilds:
                    playerMember = await guild.fetch_member(playerId)
                    if playerMember.nick:
                        current.nicknames[guild.id] = playerMember.nick
                divison.players.append(current)
                print(f"Added: {current.discordPlayerData.name} to {divison_name} division")
            
            divison.activeTurn = divison.players[0]
            await divison.find_channel(client)

    async def on_member_update(self,before,after):
        if before.nick == after.nick:
            return
        
        for division_name,division in self.divisions.items():
            for player in division.players:
                if player.discordPlayerData.id == before.id:
                    player.nicknames[after.guild.id] = after.nick
                    break

    async def on_raw_reaction_add(self,react):
        if react.user_id == client.user.id:
            return
        for division in self.divisions.values():
            await division.handle_react(react,self)

    async def on_message(self,message):
        if message.author == client.user:
            return
        
        for division in self.divisions.values():
            await division.handle_message(message,self)

        save = re.fullmatch(r"!Save",message.content,re.IGNORECASE)
        if save and message.author.id in self.admins:
            try:
                await message.channel.send("Saving to file...")
                self.saveManager.saveAll(self.divisions)
                await message.channel.send("Save completed!")
            except:
                await message.channel.send("COULD NOT SAVE")
            
        load = re.fullmatch(r"!load",message.content,re.IGNORECASE)
        if load and message.author.id in self.admins and self.saveManager.checkJson():
            

            try:
                await message.channel.send("Loading from file...")
                divisionBuffer = await self.saveManager.load(self)
                self.divisions = divisionBuffer
                for division_name, division in self.divisions.items():
                    division.timerTask = asyncio.create_task(division.run_timer())
                await message.channel.send("Load successful!")
                
            except:
                await message.channel.send("DATA UNOBTAINABLE")

        lookUp = re.fullmatch(r"!Lookup\s+(.+)",message.content,re.IGNORECASE)
        if lookUp:
            pokemonName = lookUp.group(1).strip()
            result = self.get_pokemon_info(pokemonName)

            if result:
                statuses = []
                for division_name,division in self.divisions.items():
                    draftedList = division.draftedPokemon
                    status = "already drafted" if result['name'].lower() in draftedList else "available"
                    statuses.append(f"**{division_name} division**: {status}")

                    if result['name'].lower() in division.complexBans:
                        statuses.append(f"Complex Ban for {division_name}: {division.complexBans[result['name'].lower()]}")
                
                status_str = "\n".join(statuses)

                await message.channel.send(f"**{result['name']}**\nDex #: {result['dex']}\nPoints: {result['points']}\n{status_str}")

            else:
                suggestions = difflib.get_close_matches(
                    pokemonName.lower(),
                    self.pokemon_dict.keys(),
                    n=3,
                    cutoff=0.6
                )
                if suggestions:
                    suggestion_list = ", ".join(suggestions)
                    await message.channel.send(
                        f"Pokémon '{pokemonName}' not found. Did you mean: {suggestion_list}?"
                    )
                else:
                    await message.channel.send(f"Pokémon '{pokemonName}' not found.")
            return
        
        Start = re.fullmatch(r"!StartDraft",message.content,re.IGNORECASE)
        if Start and message.author.id in self.admins:
            for division_name,division in self.divisions.items():
                #division.activeTurn = division.players[0]
                division.remainingTime = division.turnTimer

                if not division.timerTask:
                    division.timerTask = asyncio.create_task(division.run_timer())
                    
                await division.notify_current_player()
            return

        skipCmd = re.fullmatch(r"!skip\s+(.+)", message.content, re.IGNORECASE)
        if skipCmd and message.author.id in self.admins:
            division_request = skipCmd.group(1)
            for division_name,division in self.divisions.items():
                if division_request.lower() == division_name.lower() and division.activeTurn:
                    skipped_player = division.activeTurn
                    await skipped_player.discordPlayerData.send(division.adminSkippedMessage)
                    skipped_player.missedTurns += 1
                    division.turnTracker, division.forward = division.get_next_turn(division.turnTracker,division.forward)
                    division.activeTurn = division.players[division.turnTracker]
                    division.remainingTime = division.turnTimer
                    await division.draftChannel.send(f"{skipped_player.discordPlayerData.mention}'s turn in {division.name} division has been skipped.")
                    await division.notify_current_player()
                    return
            await message.channel.send("It seems I was unable to find that division.")
            return
        
        addRule = re.fullmatch(r"!addcban\s+([\w-]+)\s+(.+)", message.content, re.IGNORECASE)
        if addRule and message.author.id in self.admins:
            pokemon_request = addRule.group(1).lower()
            rule_request = addRule.group(2).lower().strip()
            if pokemon_request not in self.pokemon_dict:
                await message.channel.send(f"{pokemon_request} is not a valid Pokemon")
                return
            for division_name,division in self.divisions.items():
                division.complexBans[pokemon_request] = rule_request
                await message.channel.send(f"{rule_request} added as a rule for {pokemon_request} in {division_name}")
            return

        spreadSheet = re.fullmatch(r"!Docs", message.content, re.IGNORECASE)
        if spreadSheet:
            await message.channel.send("Iron Bundle Division:https://docs.google.com/spreadsheets/d/1GQcDmouK4coDi7XcQVpDyEp0tZhlZXp_a9F9YQ-OlLg/edit?usp=sharing\n"+
                                       "Delibird Division:https://docs.google.com/spreadsheets/d/1fs0B7jlXaQBTDM2FZV9TVPaRX_bRkWu74PRkG46GyRA/edit?usp=sharing")
            return

        currentTurn = re.fullmatch(r"!Curr_turn", message.content, re.IGNORECASE)
        if currentTurn:
            messageToSend = "Here are the current Turns:\n"
            for division_name,division in self.divisions.items():
                if division.activeTurn:
                    time_str = str(datetime.timedelta(seconds=division.remainingTime))
                    messageToSend += (f"{division_name} : {division.activeTurn.discordPlayerData}"
                            f"(Time left : {time_str})\n")
                else:
                    messageToSend += f"{division_name}: No active turn\n"
            await message.channel.send(messageToSend)
        
        showPokemon = re.fullmatch(r"!Team(\s|\Z)(.+|\Z)", message.content, re.IGNORECASE)
        if showPokemon:
            found = False
            messageToSend = ""
            nameSearch = ""

            splitMessage = re.split(r"\s+", message.content)
            if len(splitMessage) < 2:
                nameSearch = message.author.name
            else:
                nameSearch = splitMessage[1]

            for division_name,division in self.divisions.items():
                for player in division.players:
                    #Created for readability as to not have one giant if statement. May revisit in the future for refactoring but for now it works

                    if nameSearch in player.nicknames.values() or player.discordPlayerData.name == nameSearch or player.discordPlayerData.display_name == nameSearch:
                        found = True
                        if player.draftedPokemon:
                            messageToSend = f"{player.discordPlayerData.name}'s drafted Pokémon in {division_name}:\n"
                            draftedNames = [name.capitalize() for name in player.draftedPokemon.values()]
                            messageToSend += "\n".join(draftedNames)
                        else:
                            messageToSend = f"{player.discordPlayerData.name} has not drafted any Pokémon yet in {division_name}."
                        break
                if found:
                    break

            if not found:
                messageToSend = f"{nameSearch}'s team could not be found"
            await message.channel.send(messageToSend)
            return
        
        helpMessage = re.fullmatch(r"!help", message.content, re.IGNORECASE)
        if helpMessage:
            await message.channel.send("The commands for the bot are as follows:\n"
                                 "!draft (pokemon) - Use this on your turn to draft a pokemon. **This command is also exclusive to DMs**\n"
                                 "!lookup (pokemon) - find the name of a Pokémon closest to the input. This is useful if you don't know how to spell a Pokémon's name,if you're trying to find the exact format, and if you would like to know its draft status, cost, or any bans it has.\n"
                                 "!forfeit - forfeit the remainder of your picks. You may only do this if you have at least 9 Pokémon. **This action is also exclusive to DMs and cannot be reversed.**\n"
                                 "!Docs - Provides the links to the google sheet for each division.\n"
                                 "!team (user) - This will show you the pokémon the specified user has currently drafted. Leave blank to see what *you* have drafted\n"
                                 "!curr_turn - This will show whos turn it currently is for each division.\n"
                                 "*side note: none of the commands are case sensitive.*"
                                 )
            if message.author.id in self.admins:
                await message.channel.send("The admin commands for this bot are as follows:\n"
                                    "!startdraft - Use this to start the drafting process\n"
                                    "!skip (division) - Skips the current drafting person and moves on to the next player in the drafting order\n"
                                    "!addcban (pokemon) (rule) - Adds a complex ban for the specified pokemon in all divisions. This ban will be viewable with the !lookup command"
                                    )



intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.reactions = True



client = MyClient(intents = intents, max_messages = 100)

load_dotenv()
TOKEN = os.getenv("CLIENT_TOKEN")
client.run(TOKEN)