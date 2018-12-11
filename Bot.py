import discord
import os
import asyncio
import RecourceManager
import time
import ImageCreator
import cv2 as cv
import re
import operator


script_dir = os.path.dirname(__file__)
tokenfile = "tokenCookie.txt"

abs_token_path = os.path.join(script_dir, tokenfile)

client = discord.Client()
token = RecourceManager.load_token(abs_token_path)

# a list of bots. these bots will get all messages relayed to them
bots = []


def run_client():
    client.run(token)


@client.event
async def on_ready():
    print("Logged in as")
    print(client.user.name)
    print(client.user.id)
    print("------")

    for b in bots:
        await b.on_start()


@client.event
async def on_message(message):
    for b in bots:
        await b.handle_message(message)


def init_bot(bot):
    """adds the bot to the message relay"""
    bots.append(bot)


class Resteal(object):
    """Holds all information necessary to handle resteals"""
    def __init__(self, thief, endtime, golden_cookie=False, amount=1):
        self.thief = thief
        self.endtime = endtime
        self.golden_cookie = golden_cookie
        self.amount = amount

    @property
    def time(self):
        return max(0, self.endtime - time.time())


class Bot(object):
    """The Bot controls all interaction with Discord"""
    def __init__(self, name="Game"):
        # Bot settings
        self.command_prefix = "?"
        self.allow_exec = True  # if the exec command is allowed
        self.exec_users = ["159065682137317376"]  # a list of users that can use exec

        self.print_buffer = []  # a list of strings that will be send as soon as possible (for exec)
        self.more_mentions = False  # use more mentions

        # Game settings ==============================================================
        self.start_cookies = 10  # the amount of cookies a user starts with
        self.resteal_time_s = 60  # the seconds in which a cookie can be restolen
        self.steal_timeout = 60 * 15  # the time between stealing attempts
        self.golden_resteal_time_s = 60 * 60 * 12  # one day
        self.fed_time = 60 * 60 * 12
        self.fed_percentage = 0.8
        self.savename = "jars"
        self.name = name  # important for saving / loading games
        self.cookieking_id = "521748145646862337"
        self.quick_resteal_time = 20
        self.quick_resteal_amount = 2
        self.jailtime = 60 * 60 * 24

        self.golden_owner_string = "golden_cookie"  # the string that is the key for the golden owner in the jars dict

        # variables =============================================================
        # hold the information about the amount of cookies. the key is a discord user class the value the amount of cookies
        # there is one "special" jar that is named "golden_cookie" it stores the person that currently holds the golden cookie
        self.jars = {}
        self.load_jars()

        self.criminal_score = {}
        self.jail_role_id = "522038962299207700"
        self.jail_times = {}  # the user in jail and the time

        self.resteals = {}  # the resteals associated with the victim user (the user that can resteal)
        self.stealstops = {}  # the stealstop time associated with the user that can't steal anymore
        self.fed_times = {}  # the time people until fed people are not fed anymore (anyone not in here is not fed)

        self.criminal_increases = {
            "zero_cookies": 5,
            "poor": 1,
            "offline": 5,
            "bot": 1,
            "cooldown": 2,
            "normal": -1,
            "rich": -5,
            "cookie_king": -10,
            "author_offline": 20,
        }

    def load_jars(self):
        self.jars = RecourceManager.load_dict("jars" + self.name)

    def save_jars(self):
        RecourceManager.save_dict(self.jars, "jars" + self.name)

    # utility functions =============================================================
    async def on_start(self):
        for s in client.servers:
            for m in s.members:
                if self.jail_role_id in [r.id for r in m.roles]:
                    await client.remove_roles(m, self.get_role(s, self.jail_role_id))

    async def jail(self, user, channel):
        self.jail_times[user] = time.time() + self.jailtime
        await client.send_message(channel, "%s you are jailed for %ih for your criminal acts!" % (self.get_mention(user), self.jailtime // 3600))
        self.criminal_score[user] = 0
        if self.jail_role_id:
            jail_role = self.get_role(channel.server, self.jail_role_id)
            if jail_role:
                await client.add_roles(user, jail_role)
            else:
                print("ERROR no jail role found at this id: %s" % self.jail_role_id)

    async def check_jail(self, user, channel):
        if self.get_jail_time(user):
            self.jail_times[user] += 60 * 60
            await client.send_message(channel, "%s your jailtime increased by 1h for being naughty" % self.get_mention(user))
            return True
        # umjail the user
        if user in self.jail_times:
            del self.jail_times[user]
            await client.send_message(channel, "%s you are free now! Go fly . . . to the sky" % self.get_mention(user))
        if self.jail_role_id:
            jail_role = self.get_role(channel.server, self.jail_role_id)
            if jail_role:
                await client.remove_roles(user, jail_role)
            else:
                print("ERROR no jail role found at this id: %s" % self.jail_role_id)
        return False

    async def add_criminal_score(self, user, amount, channel, quote="", message=True):
        if message:
            await client.send_message(channel, quote + "%s Your criminal score %s by %i." % (self.get_mention(user), "increased" if amount > 0 else "decreased", abs(amount)))
        if not user in self.criminal_score:
            self.criminal_score[user] = 0
        self.criminal_score[user] += max(amount, 0)
        if self.criminal_score[user] >= 100:
            await self.jail(user, channel)

    def get_jail_time(self, user):
        return max(0, self.jail_times[user] - time.time()) if user in self.jail_times else 0

    def get_criminal_score(self, user):
        return self.criminal_score[user] if user in self.criminal_score else 0

    @property
    def golden_owner(self):
        """gets the golden owner

        :return: the owner of the golden cookie. None if there is none
        """
        return self.jars[self.golden_owner_string] if self.golden_owner_string in self.jars else None

    @golden_owner.setter
    def golden_owner(self, value):
        """sets the golden owner

        :param value: the new golden owner
        :return:
        """

        self.jars[self.golden_owner_string] = value

    @golden_owner.deleter
    def golden_owner(self):
        del self.jars[self.golden_owner_string]

    def get_user(self, id):
        for u in self.jars.keys():
            if u.id == id:
                return u

    def debug_print(self, *args):
        self.print_buffer.append(' '.join(list(map(str, args))))

    def ifnew(self, user):
        if not user in self.jars:
            self.jars[user] = self.start_cookies

    def get_stealstop(self, user):
        if user in self.stealstops:
            return self.stealstops[user]
        else:
            return 0

    def get_stealtime(self, user):
        return max(0, self.get_stealstop(user) - time.time())

    def get_mention(self, user):
        """returns mention or name depending on settings

        :param user:
        :return: string (mention or name)
        """
        return user.mention if self.more_mentions else "**{}**".format(user.name)

    def isfed(self, user):
        return user in self.fed_times and self.fed_times[user] > time.time()

    def add_resteal(self, user, resteal):
        if not user in self.resteals:
            self.resteals[user] = []
        self.resteals[user].append(resteal)

    def get_role(self, server, id):
        for r in server.roles:
            if r.id == id:
                return r
        return None
        
    def get_current_user(self, user, server):
        """returns the updated version of the user in question"""
        for m in server.members:
            if m == user:
                return m
        print("ERROR no user found")
        return None

    def get_cookie_king(self, server):
        for member in server.members:
            if self.cookieking_id in list(map(lambda x: x.id, member.roles)):
                return member
        return None

    async def check_cookie_king(self, server, channel):
        cpydct = self.jars.copy()
        if self.golden_owner_string in cpydct:
            del cpydct[self.golden_owner_string]

        key_max = max(cpydct.keys(), key=(lambda x: cpydct[x]))
        max_user = self.get_current_user(key_max, server)

        if not self.cookieking_id in list(map(lambda x: x.id, max_user.roles)):
            cookie_king = self.get_cookie_king(server)
            if cookie_king:
                await client.remove_roles(cookie_king, self.get_role(server, self.cookieking_id))
            await client.add_roles(max_user, self.get_role(server, self.cookieking_id))
            await client.send_message(channel, "congratulations %s you are the new cookie king" % self.get_mention(max_user))

    # Command funcitons ===================================================================

    async def print_stealtime(self, author, mentions, channel, param):
        """prints the time a user has left to steal"""
        self.ifnew(author)
        stealtime = self.get_stealtime(author)
        mention = self.get_mention(author)
        if stealtime == 0:
            await client.send_message(channel, "%s you can steal again. be sneaky!" % mention)
        elif stealtime < 60:
            await client.send_message(channel, "%s you can steal again in %2i seconds" % (mention, stealtime))
        else:
            await client.send_message(channel, "%s you can steal again in %2i minutes" % (mention, stealtime // 60))
        return

    async def print_help(self, author, mentions, channel, param):
        mention = self.get_mention(author)
        lines = [
            "**jar** tells you how much cookies you have in your jar",
            "**criminality** tells you how criminal you are",
            "**jailtime** tells you how much time you have left in jail",
            "**steal <@mention>** you try to steal one cookie from the mentioned person",
            "**stop** you block all steals directed at you",
            "**gift <n> <@mention>** you gift n cookies to @mention",
            "**time** will tell you how long until you can steal again",
            "**stealgolden** <@mention> steals the golden cookie",
            "**rank** prints out the rankings",
            "**eat** you eat a cookie and gain {}% stealspeed for {} hours".format(round((1 - self.fed_percentage) * 100), int(self.fed_time // 3600)),
            "**help** shows you this list",
        ]

        if author.server_permissions.administrator:
            lines += [
                "\n**ADMIN COMMANDS**:\n"
                "**give_gold** <@mention> gives the golden cookie to the mentioned user",
                "**print_settings** prints the settings (object dictionary)",
            ]

        await client.send_message(channel, "\n" + mention + " " + "commands:\n" + "\n".join(lines))

    async def print_rankings(self, author, mentions, channel, param):
        """prints rankings and highlights the author

        :param channel: the channel that is printed onto
        :param author:
        :return: None
        """

        author_str = author.name if author else ""

        mylist = [(user, value) for user, value in self.jars.items() if isinstance(value, int)]
        mylist.sort(key=lambda x: x[1], reverse=True)
        golden_owner = self.golden_owner
        send_list = ["{:<12} {:<10}{:<5}{:<5}".format(l[0].name + "(j)" if self.get_jail_time(l[0]) else l[0].name, str(l[1]) + "(g)" if l[0] == golden_owner else str(l[1]), self.get_criminal_score(l[0]),"  <--" if l[0] == author_str else "") for l in mylist]
        await client.send_message(channel, "rankings: ```\n{:<10}{:<10}{:<10}\n".format("USER", "COOKIES", "CRIME") + "\n".join(send_list) + "\n```")

    async def print_jailtime(self, author, mentions, channel, param):
        jailtime = self.get_jail_time(author)
        if jailtime:
            if jailtime > 3600:
                timestr = "{}h".format(int(jailtime // 3600))
            elif jailtime > 60:
                timestr = "{}m".format(int(jailtime // 60))
            else:
                timestr = "{}s".format(int(jailtime))
            await client.send_message(channel, "%s you are jailed for: %s" % (self.get_mention(author), timestr))
        else:
            await client.send_message(channel, "%s you are free." % self.get_mention(author))

    async def print_jar(self, author, mentions, channel, param):
        self.ifnew(author)
        img = ImageCreator.build_cookie_jar(self.jars[author], self.golden_owner == author)
        cv.imwrite("export.png", img)
        await client.send_file(channel, "export.png", content="%s you have %i cookies %s" % (self.get_mention(author),
        self.jars[author], "and the golden" if self.golden_owner == author else ""))

    async def steal(self, author, mentions, channel, param):
        mention = self.get_mention(author)

        # check for correct arguments
        if not mentions or len(mentions) > 1:
            await client.send_message("%s wrong arguments check %shelp" % (mention, self.command_prefix))
            return

        victim = mentions[0]

        # check other stuff
        if str(author.status) == "offline":
            await client.send_message(channel, "%s you cannot steal while offline " % mention)
            await self.add_criminal_score(author, self.criminal_increases["author_offline"], channel)
            return
        if "bot" in map(lambda x: x.lower(), map(lambda x: x.name, victim.roles)):
            await client.send_message(channel, "%s you cannot steal from **%s** because he/she is a bot" % (
            mention, victim.name))
            await self.add_criminal_score(author, self.criminal_increases["bot"], channel)
            return
        if str(victim.status) == "offline":
            await client.send_message(channel, "%s you cannot steal from **%s** because he/she is offline" % (
            mention, victim.name))
            await self.add_criminal_score(author, self.criminal_increases["offline"], channel)
            return
        if self.get_stealtime(author) > 0:
            await self.print_stealtime(author, mentions, channel, param)
            await self.add_criminal_score(author, self.criminal_increases["cooldown"], channel)
            return
        if await self.check_jail(author, channel):
            return

        self.ifnew(victim)

        if self.jars[victim] < 1:
            await client.send_message(channel, "**%s** has no cookies to steal. poor him :/" % victim.name)
            await self.add_criminal_score(author, self.criminal_increases["zero_cookies"], channel)
            return

        if author.id == "159065682137317376":
            await client.send_message(channel, "%s stop stealing motherfucker" % author.mention)

        # cansteal
        victim_mention = self.get_mention(victim)

        if self.get_cookie_king(channel.server) == author:
            await self.add_criminal_score(author, self.criminal_increases["cookie_king"], channel, message=False)
        elif self.jars[victim] == 1:
            await self.add_criminal_score(author, self.criminal_increases["poor"], channel, quote="{} is poor. ".format(victim_mention))
        elif self.jars[victim] > 10:
            await self.add_criminal_score(author, self.criminal_increases["normal"], channel, message=False)
        elif self.jars[victim] > 25:
            await self.add_criminal_score(author, self.criminal_increases["rich"], channel, message=False)

        self.ifnew(author)
        self.jars[victim] -= 1
        self.jars[author] += 1
        r_time = int(self.resteal_time_s * self.fed_percentage) if self.isfed(author) else self.resteal_time_s
        message = await client.send_message(channel, "%s stole from %s he/she has %is to steal it back! (type ?stop) or click 🛑 to stop or click 🔫 to try to quick steal" % (
        mention, victim_mention, r_time))

        # add a resteal
        resteal = Resteal(author, time.time() + r_time)
        self.add_resteal(victim, resteal)
        # add a stealstop so that the user cant spam steal
        self.stealstops[author] = time.time() + self.steal_timeout
        self.save_jars()

        # add a reaction
        await client.add_reaction(message, "🛑")
        await client.add_reaction(message, "🔫")

        # now wait and then check if it has been restolen
        # await asyncio.sleep(r_time)

        temp = await client.wait_for_reaction(user=victim, timeout=r_time)
        if temp:
            reaction = temp[0]
            user = temp[1]
            if reaction.emoji == "🛑":
                await self.stop(user, [], channel, [])
            elif reaction.emoji == "🔫":
                self.resteals[victim].remove(resteal)
                # try to steal more cookies back
                amount = min(self.jars[author], self.quick_resteal_amount + 1)
                if amount:
                    self.jars[author] -= amount
                    self.jars[victim] += amount
                    self.save_jars()
                    if amount > 1:  # stole more back then you thought
                        r_time = int(self.quick_resteal_time * self.fed_percentage) if self.isfed(author) else self.resteal_time_s
                        resteal = Resteal(victim, time.time() + r_time, amount=amount)
                        self.add_resteal(author, resteal)
                        message = await client.send_message(channel, "%s quickstole %i cookies from %s. He has %i seconds to stop you" % (victim_mention, amount, mention, r_time))
                        await client.add_reaction(message, "🛑")
                        temp = await client.wait_for_reaction(user=author, timeout=r_time)
                        if temp:
                            reaction = temp[0]
                            user = temp[1]
                            await self.stop(user, [], channel, [])
                    else:  # stole back the one you got
                        await client.send_message(channel, "%s stole back his cookie from %s. He tried to steal more but %s is poor :/" % (mention, victim_mention, mention))
                else:
                    await client.send_message(channel, "%s you cannot quicksteal from %s because he has no cookies" % (victim_mention, mention))

            return

        await self.check_cookie_king(channel.server, channel)

        if resteal in self.resteals[victim]:
            await client.send_message(channel, "%s stole the cookie successfully from %s" % (mention, victim_mention))
            self.resteals[victim].remove(resteal)

    async def stealgolden(self, author, mentions, channel, param):
        mention = self.get_mention(author)
        if not mentions or len(mentions) > 1:
            await client.send_message("%s wrong arguments check %shelp" % (mention, self.command_prefix))
            return

        if self.get_stealtime(author):
            await self.print_stealtime(author, mentions, channel, param)
            return
        if await self.check_jail(author, channel):
            return

        # can steal
        self.golden_owner = author
        self.add_resteal(mentions[0], Resteal(author, time.time() + self.golden_resteal_time_s, golden_cookie=True))
        await client.send_message(channel, "%s you stole the golden cookie from %s" % (mention, self.get_mention(mentions[0])))

    async def gift(self, author, mentions, channel, param):
        mention = self.get_mention(author)
        if not mentions or len(mentions) > 1:
            await client.send_message("%s wrong arguments check %shelp" % (mention, self.command_prefix))
            return

        recipient = mentions[0]
        self.ifnew(recipient)
        self.ifnew(author)
        if param and param[0].isdigit():
            amount = int(param[0])
        else:
            amount = 1
        if self.jars[author] >= amount:
            self.jars[author] -= amount
            self.jars[recipient] += amount
            self.save_jars()
            # check roles
            await client.send_message(channel, "%s gifted %i cookies to %s" % (mention, amount, self.get_mention(recipient)))
            await self.check_cookie_king(channel.server, channel)
        else:
            await client.send_message(channel, "%s insufficient cookies in your jar" % mention)

    async def eat(self, author, mentions, channel, param):
        mention = self.get_mention(author)
        if self.isfed(author):
            await client.send_message(channel, "%s you are still fed" % mention)
            return
        if self.jars[author] <= 0:
            await client.send_message(channel, "%s you don't have anything to eat" % mention)
            return

        if self.golden_owner:
            # only loose a cookie if there is a golden owner
            self.ifnew(self.golden_owner)
            self.jars[author] -= 1
            self.jars[self.golden_owner] += 1
            await self.check_cookie_king(channel.server, channel)

        self.fed_times[author] = time.time() + self.fed_time
        await client.send_message(channel,
                                  "%s you ate your cookie and are fed now (%i%% faster stealing for %ih) but the Krümelmonster %s stole your crumbs" % (
                                  mention, round((1 - self.fed_percentage) * 100), int(self.fed_time // 3600),
                                  self.get_mention(self.golden_owner)))

    async def stop(self, author, mentions, channel, param):
        mention = self.get_mention(author)
        if not self.resteals[author]:
            await client.send_message(channel, "%s there is nothing to steal back maybe you were too slow?" % mention)
            return
        for r in self.resteals[author]:
            if r.time:  # still enough time
                if r.golden_cookie:
                    if self.golden_owner == r.thief: # still has the golden cookie
                        await client.send_message(channel, "%s you stole the golden cookie back" % mention)
                        self.golden_owner = author
                    else:
                        await client.send_message(channel, "%s you are trying to get the golden cookie from %s yet he does not posses it anymore" % (mention, self.get_mention(r.thief)))
                        return
                else:
                    self.ifnew(r.thief)
                    if self.jars[r.thief] > 0:
                        self.ifnew(author)
                        amount = min(r.amount, self.jars[r.thief])  # you can only steal as many cookies back as the person has
                        self.jars[r.thief] -= amount
                        self.jars[author] += amount
                        await client.send_message(channel,
                                                  "%s you stole %i cookie back from %s with %2is remaining!" % (
                                                  mention, amount, r.thief.mention, r.endtime - time.time()))
                        self.save_jars()
                    else:
                        await client.send_message(channel, "%s has no cookies anymore. you can't steal it back" % self.get_mention(r.thief))
            else:
                await client.send_message(channel, "%s you were too late!" % mention)
        self.resteals[author] = []  # memory leak?

    async def criminality(self, author, mentions, channel, param):
        if self.get_criminal_score(author) > 30:
            add_string = ". You can decrease your criminality by stealing from rich users. The richer the better."
        else:
            add_string = ""
        await client.send_message(channel, "%s you criminality is %i%s" % (self.get_mention(author), self.get_criminal_score(author), add_string))

    # admin commands =====================================================
    async def give_gold(self, author, mentions, channel, param):
        mention = self.get_mention(author)
        if not mentions or len(mentions) > 1:
            await client.send_message("%s wrong arguments check %shelp" % (mention, self.command_prefix))
            self.save_jars()
            return

        self.golden_owner = mentions[0]
        await client.send_message(channel, "%s you gave %s the golden cookie" % (mention, self.get_mention(mentions[0])))

    async def print_settings(self, author, mentions, channel, param):
        await client.send_message(channel, ("\n%s settings: ```\n" + "\n".join(list(self.__dict__.keys())) + "\n```") % self.get_mention(author))

    async def test(self, author, mentions, channel, param):
        await self.add_criminal_score(author, 90, channel)

    async def handle_message(self, message):
        commands = {
            "time": self.print_stealtime,
            "help": self.print_help,
            "jar": self.print_jar,
            "rank": self.print_rankings,
            "steal": self.steal,
            "stealgolden": self.stealgolden,
            "gift": self.gift,
            "eat": self.eat,
            "stop": self.stop,
            "criminality": self.criminality,
            "jailtime": self.print_jailtime,
        }

        admin_commands = {
            "give_gold": self.give_gold,
            "print_settings": self.print_settings,
            "test": self.test,
        }

        if message.content.startswith(self.command_prefix):
            author = message.author
            channel = message.channel
            com_list = message.content[len(self.command_prefix):].split()
            command = com_list[0]
            mentions = message.mentions

            if command == "exec":
                if author.id in self.exec_users and self.allow_exec:
                    # execute the following code
                    result = re.search(r"```Python(.*)```", message.content, flags=re.DOTALL)
                    if result:
                        code = result.group(1)
                        try:
                            exec(code, self.__dict__)
                        except:
                            await client.send_message(channel, "code failed")
                        for l in self.print_buffer:
                            await client.send_message(channel, l)
                            self.print_buffer = []
                    else:
                        await client.send_message(channel, "no code found")
            elif command in commands:
                await commands[command](author, mentions, channel, com_list[1:])
            elif command in admin_commands:
                if message.author.server_permissions.administrator:
                    await admin_commands[command](author, mentions, channel, com_list[1:])
                else:
                    await client.send_message(channel, "%s incorrect permissions", self.get_mention(author))

