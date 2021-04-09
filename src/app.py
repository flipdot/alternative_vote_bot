import json
import locale
import logging
import random
import sys
import re
from pathlib import Path
from typing import List, Set

from pydiscourse.exceptions import DiscourseClientError
from pydiscourse import DiscourseClient
from constants import DISCOURSE_CREDENTIALS

locale.setlocale(locale.LC_TIME, "de_DE.UTF-8")

botnames = ["flipbot", "flipbot_test", "discobot", "alternative_vote_bot"]


def is_legal_user(user) -> bool:
    return user["active"] and "suspended_at" not in user and user["username"] not in botnames


def legal_votes(vote_list: List[str], legal_usernames: Set[str]) -> List[str]:
    return [name for name in vote_list if name.lower()[1:] in legal_usernames]


def get_legal_usernames() -> Set[str]:
    with open("users.json") as f:
        legal_users = json.load(f)
        return set([user["username"].lower() for user in legal_users if is_legal_user(user)])


def check_login(client: DiscourseClient) -> None:
    try:
        client.latest_topics()
    except DiscourseClientError as e:
        logging.error(f"Could not perform login: {e}")
        sys.exit(-1)


def send_ballot(client, username):
    res = client.create_post(
        "Heyho...\n hier mal ein kleiner Test. bitte eine Liste aus irgendwelchen usernamen (mit @) zurückschreiben. Und gerne kaputtspielen ;) (muss aber noch manuell ausführen, nicht wundern, wenn erstmal nix passiert)",
        title="1 kleine Testabstimmung", archetype="private_message",
        target_usernames=username)
    return res.get('topic_id')


def distinct(seq) -> list:
    # see https://stackoverflow.com/a/4463433
    seen = set()
    return [x for x in seq if x.lower() not in seen and not seen.add(x.lower())]


def get_vote(client: DiscourseClient, topic_id) -> list:
    posts = client.topic_posts(topic_id)["post_stream"]["posts"]
    vote_list = None
    pattern = re.compile(r'@[A-Za-zäöüÄÖÜß0-9-_]+')
    for post in posts:
        if post["yours"]:
            continue
        # print(post["cooked"])
        vote_list_this_post = pattern.findall(post["cooked"])
        # skip if we already got a list and this post is empty
        if len(vote_list_this_post) == 0 and vote_list:
            continue
        vote_list = vote_list_this_post
    if not vote_list:
        # print(f"no answer from {topic_id}")
        return []
    vote_list = list(map(lambda name: name.lower(), vote_list))
    # print(f"vote list: {distinct(vote_list)}")
    return distinct(vote_list)


def initiate_election(client: DiscourseClient, users):
    if not users:
        logging.error(f"Did not get any users :(")
        sys.exit(-4)
    topics = []
    for user in users:
        if not is_legal_user(user):
            continue
        if user["username"] not in ["anselm"]:
            continue
        print(f"sending ballot to {user['username']} ...", end="")
        topics.append(send_ballot(client, user["username"]))
        print(" done.")
        # write after each user
        with open("topics.json", "w") as f:
            json.dump(topics, f)


def remind_users(client: DiscourseClient, message: str):
    with open("topics.json") as f:
        topics = json.load(f)
    for topic_id in topics:
        if len(get_vote(client, topic_id)) > 0:
            continue
        client.create_post(message, topic_id=topic_id)


def answer_with_received_lists(client: DiscourseClient, update: bool = False):
    # answers with the list received if the last message is from user or their message was updated
    with open("topics.json") as f:
        topics = json.load(f)
    legal_usernames = get_legal_usernames()
    for topic_id in topics:
        posts = client.topic_posts(topic_id)["post_stream"]["posts"]
        last_post = posts[-1]
        # if there is nothing from the user, there is no need to answer!
        if len(posts) == 1 or (last_post["yours"] and not update):
            continue
        # we do not want to edit our reminder
        if last_post["yours"] and "Erinnerung" in last_post["cooked"]:
            continue
        vote_list = get_vote(client, topic_id)
        legal_vote_list = legal_votes(vote_list, legal_usernames)
        print(vote_list, legal_vote_list)
        message = (f"Du hast für die folgende Liste von Membern abgestimmt.\n"
                   f"Überprüfe bitte, ob alle Personen, für die du abstimmen möchtest, enthalten sind.\n"
                   # f"Um die Liste zu ändern, schicke einfach eine neue Nachricht mit deiner neuen Wahl.\n"
                   f"\n-----\n\n" +
                   # vote_list,
                   "\n".join(legal_vote_list))
        if len(legal_vote_list) == 0:
            message = "Du hast keinen mir bekannten Namen eingegeben :(\n" \
                      "Denke daran, @name zu schreiben und nur für existierende Member abzustimmen ;)"
        if len(legal_vote_list) < len(vote_list):
            message = "Für die folgenden Personen konnte nicht abgestimmt werden. Bitte überprüfe deine Eingabe." \
                      " Solltest du nichts ändern, werden diese Einträge ignoriert.\n" + \
                      ("\n".join([name for name in vote_list if name not in legal_vote_list])) + \
                      "\n\n-----\n\n" + \
                      message
        if last_post["yours"]:
            print(f"updating {last_post['id']} from\n    " + last_post['cooked'].replace('\n', '\n    ') +
                  "\nto\n    " + message.replace('\n', '\n    '))
            client.update_post(last_post["id"], message)
        else:
            print(f"sending message:\n    " + message.replace('\n', '\n    '))
            client.create_post(message, topic_id=topic_id)


def get_election_results(client: DiscourseClient) -> List[List[str]]:
    with open("topics.json") as f:
        topics = json.load(f)
    legal_usernames = get_legal_usernames()
    lists = [legal_votes(get_vote(client, topic_id), legal_usernames) for topic_id in topics]
    # output order should not depend on topic_id
    random.shuffle(lists)
    return lists


def count_election_results(client: DiscourseClient) -> int:
    lists = get_election_results(client)
    voted = len(lists) - lists.count([])
    print(f"{voted} of {len(lists)} people voted")
    return voted


def print_election_results(client: DiscourseClient) -> List[List[str]]:
    lists = get_election_results(client)
    with open("vote_lists.json", "w") as f:
        json.dump(lists, f)
    print("got the following list of votes:\n")
    print(lists)
    return lists


if __name__ == "__main__":
    client = DiscourseClient(**DISCOURSE_CREDENTIALS)
    check_login(client)
    users_json = Path("users.json")
    if users_json.exists():
        with open(users_json) as f:
            users = json.load(f)
    else:
        logging.error(f"Could not find file: {users_json}")
        sys.exit(-2)
    if "--initiate-election" in sys.argv:
        initiate_election(client, users=users)
    if "--no-answer" not in sys.argv:
        answer_with_received_lists(client, update=True)
    if "--remind-users" in sys.argv:
        idx = sys.argv.index("--remind-users")
        message = sys.argv[idx + 1]
        assert "Erinnerung" in message, "message should contain the keyword `Erinnerung`!"
        remind_users(client, message)
    count_election_results(client)
    if "--print-election-results" in sys.argv:
        print_election_results(client)
