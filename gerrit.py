from datetime import datetime
import json
from pygerrit2 import GerritRestAPI, HTTPBasicAuthFromNetrc
import pprint
import urllib

class GerritMessage(object):
  def __init__(self, rest):
    # https://gerrit-review.googlesource.com/Documentation/rest-api-changes.html#change-message-info
    self.id = rest['id']
    self.revision_num = rest['_revision_number']
    self.tag = rest.get('tag')
    self.message = rest['message']

class GerritRevision(object):
  def __init__(self, id, rest):
    # http://gerrit-review.googlesource.com/Documentation/rest-api-changes.html#revision-info
    self.id = id
    self.ref = rest['ref']
    self.number = rest['_number']
    self.commit_message = ''.join(rest['commit_with_footers'])
    self.uploader_name = ''.join(rest['uploader']['name'])
    self.uploader_email = ''.join(rest['uploader']['email'])

class GerritChange(object):
  def __init__(self, url, rest):
    # https://gerrit-review.googlesource.com/Documentation/rest-api-changes.html#change-info
    self.base_url = url
    self.id = rest['id']
    self.change_id = rest['change_id']
    self.number = rest['_number']
    # yyyy-mm-dd hh:mm:ss.fffffffff
    self.last_updated = datetime.strptime(rest['updated'][:-10],
                                          '%Y-%m-%d %H:%M:%S')
    self.status = rest['status']
    self.subject = rest['subject']
    self.project = rest['project']
    self.current_revision = GerritRevision(
            rest['current_revision'],
            rest['revisions'][rest['current_revision']])

    self.messages = []
    for m in rest['messages']:
      self.messages.append(GerritMessage(m))

    self.vote_code_review = []
    self.__parse_votes(rest, self.vote_code_review, 'Code-Review')
    self.vote_commit_queue = []
    self.__parse_votes(rest, self.vote_commit_queue, 'Commit-Queue')
    self.vote_trybot_ready = []
    self.__parse_votes(rest, self.vote_trybot_ready, 'Trybot-Ready')
    self.vote_verified = []
    self.__parse_votes(rest, self.vote_verified, 'Verified')


  def __parse_votes(self, rest, array, label):
    values = rest['labels'][label].get('all')
    if not values:
      return
    for l in values:
      value = l.get('value')
      if value:
        array.append(value)

  def url(self):
    return '{}/c/{}/+/{}'.format(self.base_url, self.project, self.number)

  def is_merged(self):
    return self.status == 'MERGED'

  def is_reviewed(self):
    return 2 in self.vote_code_review

  def is_verified(self):
    return 1 in self.vote_verified

  def is_cq_ready(self):
    return 1 in self.vote_commit_queue

  def is_trybot_ready(self):
    return 1 in self.vote_trybot_ready


class Gerrit(object):
  def __init__(self, url):
    auth = HTTPBasicAuthFromNetrc(url=url)
    self.rest = GerritRestAPI(url=url, auth=auth)
    self.url = url
    self.change_options = ['CURRENT_REVISION', 'MESSAGES', 'DETAILED_LABELS',
                           'DETAILED_ACCOUNTS', 'COMMIT_FOOTERS']

  def get_change(self, change_id):
    uri = '/changes/{}?o={}'.format(change_id, '&o='.join(self.change_options))
    rest = self.rest.get(uri)
    return GerritChange(self.url, rest)

  def get_related_changes(self, change):
    uri = '/changes/{}/revisions/current/related'.format(change.id)
    changes = []
    for c in self.rest.get(uri)['changes']:
      changes.append(self.get_change(c['change_id']))
    return changes

  def query_changes(self, status=None, message=None, after=None, age_days=None,
                    change_id=None, change_num=None):
    query = []
    if message:
      query.append('message:"{}"'.format(urllib.parse.quote(message)))
    if status:
      query.append('status:{}'.format(status))
    if after:
      query.append('after:"{}"'.format(after.isoformat()))
    if age_days:
      query.append('age:{}d'.format(age_days))
    if change_id:
      query.append('change:{}'.format(change_id))
    if change_num:
      query.append('change:{}'.format(change_num))


    uri = '/changes/?q={}&o={}'.format('+'.join(query),
                                       '&o='.join(self.change_options))
    changes = []
    for c in self.rest.get(uri):
      changes.append(GerritChange(self.url, c))
    return changes

  def get_patch(self, change):
    uri = '/changes/{}/revisions/{}/patch'.format(change.id,
                                                  change.current_revision.id)
    return self.rest.get(uri)

  def get_messages(self, change):
    uri = '/changes/{}/messages'.format(change.id)
    return self.rest.get(uri)

  def review(self, change, tag, message, notify_owner, vote_code_review=None,
             vote_verified=None, vote_cq_ready=None, vote_trybot_ready=None):
    review = {
        'tag': tag,
        'message': message,
        'notify': 'OWNER' if notify_owner else 'NONE',
    }

    labels = {}
    if vote_code_review:
      labels['Code-Review'] = vote_code_review
    if vote_verified:
      labels['Verified'] = vote_verified
    if vote_cq_ready:
      labels['Commit-Queue'] = vote_cq_ready
    if vote_trybot_ready:
      labels['Trybot-Ready'] = vote_trybot_ready

    if labels:
      review['labels'] = labels

    #pprint.PrettyPrinter(indent=4).pprint(review)
    return self.rest.review(change.id, change.current_revision.id,
                            json.dumps(review))

