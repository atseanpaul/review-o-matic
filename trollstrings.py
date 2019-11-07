class ReviewStrings(object):
  HEADER='''
-- Automated message --
'''
  GREETING='''
Hi {},
Thank you for your patch, I had a {} time reading through it! Here is some
feedback for you.
'''
  FOUND_ISSUES_HEADER_SINGLE='''
The following issue was found with your patch:
'''
  FOUND_ISSUES_HEADER_MULTIPLE='''
The following issues were found with your patch:
'''
  SUCCESS='''
No changes have been detected between this change and its upstream source!
'''
  POSITIVE_VOTE='''
This patch is certified {} by review-o-matic!
'''
  CLEAN_BACKPORT_HEADER='''
This change has a BACKPORT prefix, however it does not differ from its upstream
source. The BACKPORT prefix should be primarily used for patches which were
altered during the cherry-pick (due to conflicts or downstream inconsistencies).
'''
  MISSING_FIELDS='''
Your commit message is missing the following required field(s):
    {}
'''
  FEEDBACK_AFTER_ISSUES='''
Enough with the bad news! Here's some more feedback on your patch:
'''
  MISSING_HASH_HEADER='''
Your commit message is missing the upstream commit hash. It should be in the
form:
'''
  MISSING_HASH_FOOTER='''
Hint: Use the '-x' argument of git cherry-pick to add this automagically
'''
  INVALID_HASH_HEADER='''
The commit hash(es) you've provided in your commit message could not be found
upstream. The following hash/remote/branch tuple(s) were tried:
'''
  INVALID_HASH_LINE='''
  {}
'''
  MISSING_AM='''
Your commit message is missing the patchwork URL. It should be in the
form:
    (am from https://patchwork.kernel.org/.../)
'''
  DIFFERS_HEADER='''
This patch differs from the source commit.
'''
  ALTERED_UPSTREAM='''
Since this is not labeled as BACKPORT, it shouldn't. Either this reviewing
script is incorrect (totally possible, pls send patches!), or something changed
when this was backported. If the backport required changes, please consider
using the BACKPORT label with a description of your downstream changes in your
commit message

Below is a diff of the upstream patch referenced in this commit message, vs this
patch.

'''
  ALTERED_FROMLIST='''
Changes have been detected between the patch on the list and this backport.
Since the diff algorithm used by the developer to generate this patch may
differ from the one used to review, this could be a false negative.

If the backport required changes to the FROMLIST patch, please consider adding
a BACKPORT label to your subject.

Below is the generated diff of the fromlist patch referenced in this commit
message vs this patch.

'''
  BACKPORT_FROMLIST='''
Below is the generated diff of the fromlist patch referenced in this commit
message vs this patch. This message is posted to make reviewing backports
easier.

Since the diff algorithm used by the developer to generate this patch may
differ from the one used to review, there is a higher chance that this diff is
incorrect. So take this with a grain of salt.

'''
  CLEAR_VOTES='''
Changes were detected between this patch and the upstream version referenced in
the commit message.

Comparing FROMLIST backports is less reliable than UPSTREAM/FROMGIT patches
since the diff algorithms can differ between developer machine and this
review script. As such, it's usually not worthwhile posting the diff. Looks like
you'll have to do this review the old fashioned way!
'''
  BACKPORT_DIFF='''
This is expected, and this message is posted to make reviewing backports easier.

'''
  FOUND_FIXES_REF_HEADER='''
 !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
 !! NOTE: This patch has been referenced in the Fixes: tag of another commit. If
 !!       you haven't already, consider backporting the following patch[es]:'''
  FIXES_REF_LINE='''
 !!  {}'''
  FIXES_REF_FOOTER='''
 !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
'''
  FOOTER='''
To learn more about backporting kernel patches to Chromium OS, check out:
https://chromium.googlesource.com/chromiumos/docs/+/master/kernel_faq.md#UPSTREAM_BACKPORT_FROMLIST_and-you

If you're curious about how this message was generated, head over to:
https://github.com/atseanpaul/review-o-matic

This link is not useful:
https://thats.poorly.run/
'''
  ISSUE_SEPARATOR='''
>>>>>>> Issue {}
'''
  FEEDBACK_SEPARATOR='''
>>>>>> Feedback {}
'''
  REVIEW_SEPARATOR='''
------------------
'''
  WEB_LINK='''
If you would like to view the upstream patch on the web, follow this link:
{}
'''

  GREETING_SWAG = ['amazing', 'awesome', 'beautiful', 'blithesome', 'capital',
                   'classic', 'corking', 'cracking', 'dandy', 'divine',
                   'dynamite', 'excellent', 'fabulous', 'fantabulous',
                   'fantastic', 'grand', 'great', 'groovy', 'incredible',
                   'ineffable', 'jim-dandy', 'marvelous', 'miraculous',
                   'mirthful', 'neat', 'nifty', 'out-of-sight', 'outstanding',
                   'peachy', 'quality', 'radical', 'remarkable', 'righteous',
                   'rousing', 'sensational', 'spectacular', 'splendid',
                   'stellar', 'sterling', 'stupendous', 'sublime', 'super',
                   'superb', 'supernal', 'swell', 'terrific', 'topping',
                   'unbelievable', 'wonderful', 'wondrous']

  SWAG = ['Frrrresh', 'Crisper Than Cabbage', 'Awesome', 'Ahhhmazing',
          'Cool As A Cucumber', 'Most Excellent', 'Eximious', 'Prestantious',
          'Supernacular', 'Bodacious', 'Blue Chip', 'Blue Ribbon', 'Cracking',
          'Dandy', 'Dynamite', 'Fab', 'Fabulous', 'Fantabulous',
          'Scrumtrulescent', 'First Class', 'First Rate', 'First String',
          'Five Star', 'Gangbusters', 'Grand', 'Groovy', 'HYPE', 'Jim-Dandy',
          'Snazzy', 'Marvelous', 'Nifty', 'Par Excellence', 'Peachy Keen',
          'PHAT', 'Prime', 'Prizewinning', 'Quality', 'Radical', 'Righteous',
          'Sensational', 'Slick', 'Splendid', 'Lovely', 'Stellar', 'Sterling',
          'Superb', 'Superior', 'Superlative', 'Supernal', 'Swell', 'Terrific',
          'Tip-Top', 'Top Notch', 'Top Shelf', 'Unsurpassed', 'Wonderful']
