import discord,re,asyncio,datetime
from playerClass import Player


draftMin = 9
draftMax = 12
turnDuration = 21600 #6 hours in seconds

class Division:
    
    def __init__(self,name,bot):
        self.name = name
        self.draftChannel = None
        
        self.players = []
        self.activeTurn = Player
        self.turnTracker = 0
        self.forward = True
        self.turnTimer = self.remainingTime = turnDuration
        self.draftedPokemon = []
        self.complexBans = {}
        self.draftMin = draftMin
        self.draftMax = draftMax
        self.timerTask = None
        self.roundCounter = 1
        self.savedMessageId = None
        self.savedChannelId = None
        self.savedDraftRequest = None
        self.confirmMessageId = None

        self.cantDraftMessage = "This Pokémon can’t be drafted. Try using !Lookup [pokemon] to check the spelling."
        self.positiveCantDraftMessage = "This Pokémon has already been drafted. Try another one!"
        self.draftedMessage = "{author_mention} from the {name} division has drafted {pokemon_name}! (Round {round_counter})"
        self.pointsRemainingMessage = "You have {points} points remaining."
        self.maxDraftMessage = f'Maximum reached: {self.draftMax} Pokémon drafted. You can’t draft any more—hope you enjoyed the draft!'
        self.draftEndedMessage = f'The {self.name} division draft has officially ended-good luck on your matches everyone!'
        self.forfeitReminder = "Reminder: Use \"!forfeit\" to forfeit your remaining drafts. **This cannot be undone!**"
        self.notEnoughPointsMessage = "Insufficient points for this draft. Try a different Pokémon."
        self.dexRuleMessage = "You’ve already drafted a Pokémon with this Dex number."
        self.adminSkippedMessage = "Your turn has been manually skipped by an admin."
        self.lowPointsWarning = ("**WARNING**: You have less than half of your points remaining and have not drafted the minimum number of Pokémon required for the league.\n"
                                    "To stay on track, the maximum points you can spend on a single Pokémon at this time is: {max_pick}.")
        
        #needs {POINTS_REMAINING} for format()
        with open("IntialDraftMessage.txt","r",encoding="utf-8") as f:
            self.first_draft = f.read()
         #needs {POINTS_REMAINING} and {ROUND_NUMBER} for format()
        with open("ShorterDraftMessage.txt","r",encoding="utf-8") as f:
            self.draft_msg = f.read()

    async def find_channel(self,bot):
        target = f"drafting-{self.name}" 
        for guild in bot.guilds:
            for channel in guild.text_channels:
                if target in channel.name:
                    print(f"{self.name} found its channel:{bot.get_channel(channel.id)}")
                    self.draftChannel = channel
                    return
        raise RuntimeError(f"No drafting channel found for division '{self.name}'")


    async def draft_over(self):
        self.activeTurn = None
        self.remainingTime = 0
        if self.timerTask:
            self.timerTask.cancel()
            try:
                await self.timerTask
            except asyncio.CancelledError:
                pass
            self.timerTask = None
        await self.draftChannel.send(self.draftEndedMessage)



    async def notify_current_player(self):
        if self.roundCounter == 1:
            message = self.first_draft.format(POINTS_REMAINING=self.activeTurn.points)
            await self.activeTurn.discordPlayerData.send(message)
            return
        message = self.draft_msg.format(POINTS_REMAINING=self.activeTurn.points,ROUND_NUMBER=self.roundCounter)
        await self.activeTurn.discordPlayerData.send(message)
        if self.activeTurn.capped_spending_check():
            self.activeTurn.update_single_turn_spend()
            message = self.lowPointsWarning.format(max_pick = self.activeTurn.maxSingleTurnSpend)
            await self.activeTurn.discordPlayerData.send(message)
        if self.activeTurn.pokemon_count() >= self.draftMin:
            await self.activeTurn.discordPlayerData.send(self.forfeitReminder)
    


    def forfeit(self,currentIndex,forward):
        if not self.players:
            return None,None
        
        oldForward = forward

        if forward:
            if currentIndex >= len(self.players):
                currentIndex = len(self.players)-1
        else:
            currentIndex -= 1
            if currentIndex < 0:
                currentIndex = 0
                forward = True

        if forward != oldForward:
            self.roundCounter += 1

        return currentIndex,forward


    def get_next_turn(self,currentIndex,forward):
        oldForward = forward
        if forward:
            currentIndex += 1
            if currentIndex >= len(self.players):
                currentIndex = len(self.players) - 1
                forward = False
        else:
            currentIndex -= 1
            if currentIndex < 0:
                currentIndex = 0
                forward = True

        if forward != oldForward:
            self.roundCounter += 1

        if self.roundCounter >=self.draftMax:
           asyncio.create_task(self.draft_over())

        return currentIndex, forward
    
    async def next_turn_procedure(self):
        self.activeTurn = self.players[self.turnTracker]
        self.remainingTime = self.turnTimer
        await self.notify_current_player()
    
    async def run_timer(self):
        while True:
            now = datetime.datetime.now().time()
            if not (datetime.time(2,0)<= now < datetime.time(8,0)):
                if self.remainingTime > 0:
                    self.remainingTime -= 1
                    print(self.remainingTime)
                
            if self.remainingTime <= 0:
                await self.timeout_turn()
            await asyncio.sleep(1)
    
    async def timeout_turn(self):
        timed_out = self.activeTurn
        await self.draftChannel.send(f"{timed_out.discordPlayerData.mention} didn’t make their move in time! On to the next turn…")
        timed_out.missedTurns += 1
        self.turnTracker,self.forward = self.get_next_turn(self.turnTracker,self.forward)
        self.activeTurn = self.players[self.turnTracker]
        self.remainingTime = self.turnTimer
        await self.notify_current_player()


    def clearRequestcache(self):
        self.savedChannelId = None
        self.savedDraftRequest = None
        self.savedMessageId = None
        self.confirmMessageId = None


    async def handle_react(self,react,bot):
        if react.message_id != self.confirmMessageId:
            return
        channel = await bot.fetch_channel(self.savedChannelId)
        message = await channel.fetch_message(self.savedMessageId)
        
        if str(react.emoji) == "🚫":
            self.clearRequestcache()
            await channel.send("Choice cancelled. Please select new choice.")
            return
        if str(react.emoji) == "✅":
            await self.handle_draft(message,self.savedDraftRequest,bot)
            self.clearRequestcache()
    

    async def handle_message(self,message,bot):

        if not isinstance(message.channel,discord.DMChannel):
            return
        if getattr(self.activeTurn,"discordId",None) != message.author.id:
            return
        #hijacked orginal draft request handling to have message confirmation added. Will revisit post season...
        draft = re.fullmatch(r"!draft\s+(.+)", message.content, re.IGNORECASE)
        if(draft):
            self.savedDraftRequest = draft.group(1).strip().lower()
            self.savedChannelId = message.channel.id
            self.savedMessageId = message.id
            warningMessage = ""
            if self.savedDraftRequest in self.complexBans:
                warningMessage = (f"**Warning** {self.savedDraftRequest.capitalize()} has the following complex bans: "
                                  f"{self.complexBans[self.savedDraftRequest]}")
            sentMessage = await message.channel.send(f"React to confirm drafting {self.savedDraftRequest.capitalize()}.\n{warningMessage}")
            await sentMessage.add_reaction("✅")
            await sentMessage.add_reaction("🚫")
            self.confirmMessageId = sentMessage.id
            return
        
        forfeit = re.fullmatch(r"!forfeit", message.content, re.IGNORECASE)
        if forfeit:
            await self.handle_forfeit(message,bot)
            return
        
    async def handle_draft(self,message,pokemonRequested,bot):
        PokemonData = bot.get_pokemon_info(pokemonRequested)
        if PokemonData == None:
            await message.channel.send(self.cantDraftMessage)
            return
        if PokemonData['name'].lower() in self.draftedPokemon:
            await message.channel.send(self.positiveCantDraftMessage)
            return
        PokedexNumber = PokemonData['dex']
        PokemonCost = PokemonData['points']
        PokemonName = PokemonData['name'].lower()
        if "mega-" not in PokemonName:
            draft_status = self.activeTurn.attempt_draft(PokedexNumber,PokemonName,PokemonCost)
        else:
            draft_status = self.activeTurn.attempt_captain_draft(PokedexNumber,PokemonName,PokemonCost)
        AnnounceDraftedMessage = self.draftedMessage.format(
                    author_mention = message.author.mention,
                    name = self.name,
                    pokemon_name = PokemonName.capitalize(),
                    round_counter = self.roundCounter
                )
        match draft_status:
            #success
            case 0:
                self.draftedPokemon.append(PokemonName)
                await self.draftChannel.send(AnnounceDraftedMessage)
                followUpMessage = self.pointsRemainingMessage.format(points = self.activeTurn.points)
                await message.channel.send(followUpMessage)
                await message.channel.send(f"You also have {self.activeTurn.captainPoints} captain points remaining.")
                #can't draft again
                if self.activeTurn.pokemon_count()>= self.draftMax or self.activeTurn.points == 0:
                    if self.activeTurn.pokemon_count() >= self.draftMax:
                        await message.channel.send(self.maxDraftMessage)
                    else:
                        await message.channel.send("You have run out of points. I hope you enjoyed the draft!")
                        await self.announcements.send(f"{message.author.mention} has used all their points and is done drafting!")

                    self.players.remove(self.activeTurn)
                    self.turnTracker,self.forward = self.forfeit(self.turnTracker,self.forward)
                    if not self.players:
                        await self.draft_over()
                        return
                    if self.turnTracker >= len(self.players):
                        #edge case for removal 
                        self.turnTracker = len(self.players) - 1 if not self.forward else 0
                    self.activeTurn = self.players[self.turnTracker]
                else:
                    self.turnTracker,self.forward = self.get_next_turn(self.turnTracker,self.forward)
                await self.next_turn_procedure()
            #not enough points
            case 1:
                await message.channel.send(self.notEnoughPointsMessage)
            #dex rule
            case 2:
                await message.channel.send(self.dexRuleMessage)
            #more then one draft for turn
            case 3:
                self.draftedPokemon.append(PokemonName)
                await self.draftChannel.send(AnnounceDraftedMessage)
                await message.channel.send(f"**It's still your turn!** You have {self.activeTurn.missedTurns + 1} Pokémon left to draft.")
            case 4:
                await message.channel.send(self.lowPointsWarning.format(max_pick=self.activeTurn.maxSingleTurnSpend))
                await message.channel.send("Due to this fact your draft request could not be complete. please draft another Pokémon.")
            case 5:
                await message.channel.send(self.notEnoughPointsMessage)
                await message.channel.send(f"You have {self.activeTurn.captainPoints} points for your captain.")
            case 6:
                await message.channel.send("You are at your captain limit.")
            case _:
                await message.channel.send("Unable to complete draft request, please contact Jex(Justin) or Zack(League Runner)")
        return

    async def handle_forfeit(self,message,bot):
        if self.activeTurn.pokemon_count() < self.draftMin:
            await message.channel.send("You must have at least 9 Pokémon drafted before you can forfeit your remaining turns.")
            return
        await message.channel.send("You’ve chosen to forfeit your remaining drafts.")
        await self.draftChannel.send(f"{message.author.mention} chose to forfeit their remaining drafts.")

        self.players.remove(self.activeTurn)
        if not self.players:
            await self.draft_over()
            return

        
        self.turnTracker,self.forward = self.forfeit(self.turnTracker,self.forward)
        self.next_turn_procedure()
        return
    
    def toJSON(self):
        return dict(
            draftChannel=self.draftChannel.id,
            players=self.players,
            activeTurn=self.activeTurn.discordId,
            turnTracker=self.turnTracker,
            forward=self.forward,
            turnTimer=self.turnTimer,
            draftedPokemon=self.draftedPokemon,
            complexBans=self.complexBans,
            roundCounter=self.roundCounter,
            savedMessageId=self.savedMessageId,
            savedChannelId=self.savedChannelId,
            savedDraftRequest=self.savedDraftRequest,
            confirmMessageId=self.confirmMessageId
        )