import json
import locale
import logging
import sys
import re
from pathlib import Path

from pydiscourse.exceptions import DiscourseClientError
from pydiscourse import DiscourseClient
from constants import DISCOURSE_CREDENTIALS

locale.setlocale(locale.LC_TIME, "de_DE.UTF-8")


def check_login(client: DiscourseClient) -> None:
    try:
        client.latest_topics()
    except DiscourseClientError as e:
        logging.error(f"Could not perform login: {e}")
        sys.exit(-1)


def send_ballot(client, username):
    res = client.create_post("huhu", title="Testabstimmung y", archetype="private_message",
                             target_usernames=username)
    return res.get('topic_id')


def distinct(seq) -> list:
    # see https://stackoverflow.com/a/4463433
    seen = set()
    return [x for x in seq if x not in seen and not seen.add(x)]


def get_vote(client: DiscourseClient, topic_id) -> list:
    posts = client.topic_posts(topic_id)["post_stream"]["posts"]
    vote_list = None
    p = re.compile(r'@[A-Za-z0-9-_]+')
    for post in posts:
        if post["username"] == client.api_username:
            continue
        vote_list = p.findall(post["cooked"])
    if not vote_list:
        print(f"no answer from {topic_id}")
        return []
    vote_list = list(map(lambda name: name.lower(), vote_list))
    print(f"vote list: {distinct(vote_list)}")
    return distinct(vote_list)


def initiate_election(client: DiscourseClient, users=None):
    if not users:
        users = client.users()
        with open("users.json", "w") as f:
            json.dump(users, f)
    topics = []
    for user in users:
        if not user["active"] or "suspended_at" in user:
            continue
        if user["username"] not in ["anselm"]:
            continue
        topics.append(send_ballot(client, user["username"]))

    with open("topics.json", "w") as f:
        json.dump(topics, f)


def remind_users(client: DiscourseClient, message: str):
    with open("topics.json") as f:
        topics = json.load(f)
    for topic_id in topics:
        if len(get_vote(client, topic_id)) > 0:
            continue
        client.create_post(message, topic_id = topic_id)


def answer_with_recieved_lists(client: DiscourseClient):
    # answers if the last message is from user with the list recieved
    with open("topics.json") as f:
        topics = json.load(f)
    for topic_id in topics:
        posts = client.topic_posts(topic_id)["post_stream"]["posts"]
        last_post = posts[-1]
        if last_post["username"] == client.api_username:
            continue
        vote_list = get_vote(client, topic_id)
        client.create_post(f"Hi!\nDu hast für die folgende Liste von Membern abgestimmt.\n"
                           f"Überprüfe bitte, ob alle Personen, für die du abstimmen möchtest, enthalten sind.\n"
                           # f"Um die Liste zu ändern, schicke einfach eine neue Nachricht mit deiner neuen Wahl.\n"
                           f"\n-----\n\n" +
                           # vote_list,
                           ("\n".join(vote_list)),
                           topic_id=topic_id)


def get_election_results(client: DiscourseClient):
    with open("topics.json") as f:
        topics = json.load(f)
    for topic_id in topics:
        get_vote(client, topic_id)


if __name__ == "__main__":
    client = DiscourseClient(**DISCOURSE_CREDENTIALS)
    check_login(client)
    users_json = Path("users.json")
    if users_json.exists():
        with open(users_json) as f:
            users = json.load(f)
    else:
        users = None
    #initiate_election(client, users=users)
    remind_users(client, "Hey, voten! jetzt!! ;)")
    answer_with_recieved_lists(client)
    get_election_results(client)
