import json
from pygerrit2 import GerritRestAPI, HTTPBasicAuthFromNetrc
import urllib

class GerritMessage(object):
  def __init__(self, from_rest):
    # https://gerrit-review.googlesource.com/Documentation/rest-api-changes.html#change-message-info
    self.id = from_rest['id']
    self.revision_num = from_rest['_revision_number']
    self.tag = from_rest.get('tag')
    self.message = from_rest['message']

class GerritRevision(object):
  def __init__(self, id, from_rest):
    # http://gerrit-review.googlesource.com/Documentation/rest-api-changes.html#revision-info
    self.id = id
    self.ref = from_rest['ref']
    self.number = from_rest['_number']

class GerritChange(object):
  def __init__(self, url, from_rest):
    # https://gerrit-review.googlesource.com/Documentation/rest-api-changes.html#change-info
    self.base_url = url
    self.id = from_rest['id']
    self.change_id = from_rest['change_id']
    self.number = from_rest['_number']
    self.subject = from_rest['subject']
    self.project = from_rest['project']
    self.current_revision = GerritRevision(
            from_rest['current_revision'],
            from_rest['revisions'][from_rest['current_revision']])
    self.messages = []
    for m in from_rest['messages']:
      self.messages.append(GerritMessage(m))

  def url(self):
    return '{}/c/{}/+/{}'.format(self.base_url, self.project, self.number)

class Gerrit(object):
  def __init__(self, url):
    auth = HTTPBasicAuthFromNetrc(url=url)
    self.rest = GerritRestAPI(url=url, auth=auth)
    self.url = url

  def query_changes(self, status=None, message=None, after=None, age_days=None):
    query = []
    if message:
      query.append('message:"{}"'.format(urllib.parse.quote(message)))
    if status:
      query.append('status:{}'.format(status))
    if after:
      query.append('after:"{}"'.format(after.isoformat()))
    if age_days:
      query.append('age:{}d'.format(age_days))

    options = ['CURRENT_REVISION', 'MESSAGES']

    uri = '/changes/?q={}&o={}'.format('+'.join(query),'&o='.join(options))
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

  def review(self, change, tag, message, review_vote, notify_owner):
    review = {
        'tag': tag,
        'message': message,
        'notify': 'OWNER' if notify_owner else 'NONE',
    }
    if review_vote:
        review['labels'] = { 'Code-Review': review_vote }
    return self.rest.review(change.id, change.current_revision.id,
                            json.dumps(review))

