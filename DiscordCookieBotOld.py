import re
import discord
import asyncio
import time
import pickle
from ImageCreator import build_cookie_jar
import cv2 as cv
 
# settings ================================
 
command_prefix = "?"
start_cookies = 10  # the amount of cookies a user starts with
resteal_time_s = 60  # the seconds in which a cookie can be restolen
steal_timeout = 60 * 15  # the time between stealing attempts
golden_resteal_time_s = 60 * 60 * 12  # one day
fed_time = 60 * 60 * 12
fed_percentage = 0.8
savename = "jars"
tokenfile = "tokenCookie.txt"
 
client = discord.Client()
start_gold = "Mo0dy#5444"
 

# hold the information about the amount of cookies. the key is a discord user class the value the amount of cookies
# there is one "special" jar that is named "golden_cookie" it stores the person that currently holds the golden cookie
jars = {}
# a list of timed events associated with a user
events = {}
print_buffer = []


# dataclasses =====================================
class TimedEvent(object):
    """An object that stores a lifetime"""

    def __init__(self, endtime, type):
        self.endtime = endtime
        self.type = type

    def get_time(self):
        """returns the remaining time or 0 if less then 0"""
        return max(self.endtime - time.time(), 0)


class Stealstop(TimedEvent):
    """the stealstop is stored under the key of the person getting the stop"""
    def __init__(self, endtime):
        super().__init__(endtime, "stealstop")


class Resteal(TimedEvent):
    """An object that stores who can resteal from whom for how long"""

    def __init__(self, thief, endtime, golden_cookie=False):
        """

       :param thief: the person stealing
       :param stolen_one: the person being stolen from
       :param endtime: the time the cookie cannot be restolen after
       param golden_cookie: true if it is about the golden cookie steal
       """

        super().__init__(endtime, "resteal")

        self.thief = thief
        self.golden_cookie = golden_cookie


class Fed(TimedEvent):
    def __init__(self, endtime):
        super().__init__(endtime, "fed")


# recources ==========================================
def savejars():
    with open(savename + '.pkl', 'wb') as f:
        pickle.dump(jars, f, pickle.HIGHEST_PROTOCOL)


def loadjars():
    global jars
    try:
        with open(savename + '.pkl', 'rb') as f:
            jars = pickle.load(f)
    except:
        print("no save file yet")
        jars["golden_cookie"] = start_gold


def load_token():
    with open(tokenfile) as f:
        return f.readlines()[0].strip()


# utility ==========================================
def set_golden_owner(owner):
    """changes the owner of the golden cookie
 
    :param owner:
    :return:
    """
    jars["golden_cookie"] = owner
 
 
def get_golden_owner():
    """
 
    :return: the owner of the golden cookie
    """
    return jars["golden_cookie"] if "golden_cookie" in jars else None


def append_events(key, value):
    """appends a value to the list stored at a key or creates a new list if there is none"""
    if key in events:
        events[key].append(value)
    else:
        events[key] = [value]


def get_events(key, type):
    r_list = []
    if key in events:
        for e in events[key]:
            if e.type == type:
                r_list.append(e)
    return r_list


def give_fed(user):
    feds = get_events(user, "fed")


def remove_event(key, event):
    events[key].remove(event)


def get_user(userstr):
    for u in jars.keys():
        if u.name == userstr:
            return u
    return None


def debug_print(*args):
    print_buffer.append(' '.join(list(map(str, args))))


# actual used functions
 
@client.event
async def on_ready():
    print("Logged in as")
    print(client.user.name)
    print(client.user.id)
    print("------")


# program functions
async def print_stealtime(user, channel):
    """prints the time a user has left to steal"""
    ifnew(user)
    events = get_events(user, "stealstop")
    if events:
        stealstop = events[0]
        if stealstop.get_time():
            if stealstop.get_time() < 60:
                await client.send_message(channel, "you can steal again in %2i seconds" % stealstop.get_time())
            else:
                await client.send_message(channel, "you can steal again in %2i minutes" % (stealstop.get_time() // 60))
            return
    await client.send_message(channel, "you can steal again. be sneaky!")


def ifnew(user):
    """creates a new jar if the user is new. this needs to be checked for every involved user ever time they do something
 
   :param user: the user being checked
   :return:
   """
    if not user in jars:
        jars[user] = start_cookies
    # also check if online and if not bot


async def print_help(channel):
    lines = [
        "**?jar** tells you how much cookies you have in your jar",
        "**?steal <@mention>** you try to steal one cookie from the mentioned person",
        "**?stop** you block all steals directed torwards you",
        "**?gift <n> <@mention>** you gift n cookies to @mention",
        "**?time** will tell you how long until you can steal again",
        "**?stealgolden** <@mention> steals the golden cookie",
        "**?rank** prints out the tankings",
        "**?eat** you eat a cookie and gain {}% stealspeed for {} hours".format(round((1 - fed_percentage) * 100), int(fed_time // 3600))
    ]
    await client.send_message(channel, "commands:\n" + "\n".join(lines))


async def print_rankings(channel, author=None):
    """prints rankings and highlights the author

    :param channel: the channel that is printed onto
    :param author:
    :return: None
    """

    author_str = author.name if author else ""

    mylist = [(user.name, value) for user, value in jars.items() if isinstance(value, int)]
    mylist.sort(key=lambda x: x[1], reverse=True)
    send_list = ["{:<12} {:<5}{:<5}".format(l[0], l[1], "<--" if l[0] == author_str else "") for l in mylist]
    await client.send_message(channel, "rankings: ```\n{:<12}{:<5}\n".format("USER", "VALUE") + "\n".join(send_list) + "\n```")


@client.event
async def on_message(message):
    global events, print_buffer
    author = message.author
    channel = message.channel

    # others
    if message.content.startswith(command_prefix):
        command = message.content[1:].split()
        ifnew(author)  # create a jar if the user is new

        # check if author is fed
        feds = get_events(author, "fed")
        isfed = False
        if feds:
            f = feds[0]
            if f.get_time():
                isfed = True
            else:
                remove_event(author, f)

        if command[0] == "jar":  # give information about the contents of a users jar
            img = build_cookie_jar(jars[author], get_golden_owner() == message.author)
            cv.imwrite("export.png", img)
            await client.send_file(channel, "export.png", content=author.mention + " you have %i cookies %s" % (jars[author], "and the golden" if get_golden_owner() == author else ""))

        elif command[0] == "steal":  # try to steal from the first mentioned person
            if message.mentions:
                victim = message.mentions[0]
                if str(author.status) == "offline":
                    await client.send_message(channel, "%s you cannot steal while offline " % author.mention)
                    return
                if "bot" in map(lambda x: x.lower(), map(lambda x: x.name, victim.roles)):
                    await client.send_message(channel, "%s you cannot steal from **%s** because he is a bot" % (author.mention, victim.name))
                    return
                if str(victim.status) == "offline":
                    await client.send_message(channel, "%s you cannot steal from **%s** because he is offline" % (author.mention, victim.name))
                    return

                # check for stealstop
                stealstops = get_events(author, "stealstop")
                if stealstops and stealstops[0].get_time():
                    await print_stealtime(author, channel)
                    return
                elif stealstops:
                    remove_event(author, stealstops[0])

                ifnew(victim)

                if jars[victim] < 1:
                    await client.send_message(channel, "**%s** has no cookies to steal. poor him :/" % victim.name)
                    return
               
                if author.id == "159065682137317376":
                    await client.send_message(channel, "%s stop stealing motherfucker" % author.mention)

                # cansteal
                jars[victim] -= 1
                jars[author] += 1
                r_time = int(resteal_time_s * fed_percentage) if isfed else resteal_time_s
                await client.send_message(channel, "%s stole from %s he has %is to steal it back! (type ?stop)" % (author.mention, victim.mention, r_time))
                # add a resteal
                resteal = Resteal(author, time.time() + r_time)
                append_events(victim, resteal)
                # add a stealstop so that the user cant spam steal
                append_events(author, Stealstop(time.time() + steal_timeout))
                savejars()
                await asyncio.sleep(resteal_time_s * fed_percentage)
                if resteal in get_events(victim, "resteal"):
                    await client.send_message(channel, "%s stole the cookie successfully from %s" % (author.mention, victim.mention))
                    remove_event(victim, resteal)

        elif command[0] == "stop":  # stop all steals from you and resteal your cookies if possible
            resteals = get_events(author, "resteal")
            if not resteals:
                await client.send_message(channel, "%s there is nothing to steal back maybe you were too slow?" % author.mention)
                return

            for r in resteals:
                if r.get_time():
                    if r.golden_cookie:
                        if get_golden_owner() == r.thief:  # does he still have the cookie
                            await client.send_message(channel, "%s you stole the golden cookie back" % author.mention)
                            set_golden_owner(author)
                    else:
                        if jars[r.thief] > 0:
                            jars[r.thief] -= 1
                            jars[author] += 1
                            await client.send_message(channel, "%s you stole your cookie back from %s with %2is remaining!" %(author.mention, r.thief.mention, r.endtime - time.time()))
                            savejars()
                        else:
                            await client.send_message(channel, "%s has no cookies anymore. you can't steal it back" % r.thief.mention)
                else:
                    await client.send_message(channel, "%s you were too late!" % author.mention)
            # delete all reasteals
            for r in resteals:
                remove_event(author, r)

        elif command[0] == "gift":
            if len(message.mentions) > 0:
                recipient = message.mentions[0]
                ifnew(recipient)
                ifnew(message.author)
                if len(command) > 1 and command[1].isdigit():
                    amount = int(command[1])
                else:
                    amount = 1
                if jars[author] >= amount:
                    jars[author] -= amount
                    jars[recipient] += amount
                    savejars()
                    await client.send_message(channel, "%s gifted %i cookies to %s" % (author.mention, amount, recipient.mention))
                else:
                    await client.send_message(channel, "%s insufficient cookies in your jar" % author.mention)

        elif command[0] == "help":
            await print_help(message.channel)

        elif command[0] == "stealgolden":
            # if the owner is mentioned
            if message.mentions:
                victim = message.mentions[0]
            else:
                return
            stealstops = get_events(author, "stealstop")
            if stealstops and stealstops[0].get_time():
                await print_stealtime(author, channel)
                return
            elif stealstops:
                remove_event(author, stealstops[0])

            # cansteal
            set_golden_owner(message.author)
            append_events(author, Stealstop(time.time() + steal_timeout))
            append_events(message.mentions[0], Resteal(author, time.time() + golden_resteal_time_s, golden_cookie=True))
            await client.send_message(channel, "%s you stole the golden cookie from %s" % (author, message.mentions[0].mention))

        elif command[0] == "time":
            await print_stealtime(author, channel)

        elif command[0] == "rank":
            await print_rankings(channel, author)

        elif command[0] == "eat":
            if isfed:
                await client.send_message(channel, "%s you are still fed" % author.mention)
                return
            if jars[author] <= 0:
                await client.send_message(channel, "%s you don't have anything to eat" % author.mention)
                return
            jars[author] -= 1
            jars[get_golden_owner()] += 1
            append_events(author, Fed(time.time() + fed_time))
            await client.send_message(channel, "%s you ate your cookie and are fed now (%i%% faster stealing for %ih) but the Krümelmonster %s stole your crumbs" % (author.mention, round((1 - fed_percentage) * 100), int(fed_time // 3600), get_golden_owner().mention))

        # exec
        elif command[0] == "exec":
            if message.author.id == "159065682137317376":
                # execute the following code
                result = re.search(r"```Python(.*)```", message.content, flags=re.DOTALL)
                if result:
                    code = result.group(1)
                    try:
                        exec(code, globals())
                    except:
                        await client.send_message(channel, "code failed")
                    for l in print_buffer:
                        await client.send_message(channel, l)
                        print_buffer = []
                else:
                    await client.send_message(channel, "no code found")
            else:
                await client.send_message(channel, "insufficient permissions")
t = load_token()
loadjars()
client.run(load_token())
