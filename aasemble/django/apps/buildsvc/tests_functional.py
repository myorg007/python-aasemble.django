import os
import re

from django.test.utils import override_settings, skipIf

from aasemble.django.apps.buildsvc.pages.basewebobject import WebObject
from aasemble.django.apps.buildsvc.pages.overcastPages import BuildPage, LogoutPage, MirrorPage, OverviewPage, ProfilePage, SourcePage

from aasemble.django.apps.buildsvc.tasks import poll_one

from aasemble.django.tests import create_session_cookie


@skipIf(os.environ.get('SKIP_SELENIUM_TESTS', '') == '1',
        'Skipping Selenium based test, because SKIP_SELENIUM_TESTS=1')
class RepositoryFunctionalTests(WebObject):
    fixtures = ['complete.json']

    def test_user_signs_up_for_signup(self):
        self.driver.get('%s%s' % (self.live_server_url, '/accounts/signup/'))
        username_input = self.driver.find_element_by_id('id_email')
        username_input.send_keys('newuser@linux2go.dk')
        password1_input = self.driver.find_element_by_id('id_password1')
        password1_input.send_keys('secret')
        password2_input = self.driver.find_element_by_id('id_password2')
        password2_input.send_keys('secret')
        signup_form = self.driver.find_element_by_id('signup_form')
        signup_form.submit()
        page_header = self.driver.find_element_by_class_name('page-header')
        text_found = re.search(r'Dashboard', page_header.text)
        self.assertNotEqual(text_found, None)

    def test_secured_pages_open_after_login(self):
        session_cookie = create_session_cookie(username='test@email.com', password='top_secret')
        self.driver.get(self.live_server_url)
        self.driver.add_cookie(session_cookie)

        # test whether sources page opens after user logs in
        self.driver.get('%s%s' % (self.live_server_url, '/buildsvc/sources/'))
        page_header = self.driver.find_element_by_class_name('page-header')
        text_found = re.search(r'Sources', page_header.text)
        self.assertNotEqual(text_found, None)

    def test_source_package(self):
        '''This test performs a basic package addition and deletion.
           This test consists of following steps:
           1. Create a session cookie for given user. We are using a existing
               user 'Dennis' which is already added as fixture.
           2. Try to create a package.
           3. Verify if the package has been created.
           4. Try to delete the package
           5. Verify if the package has been deleted'''
        sourcePage = SourcePage(self.driver)
        self.create_login_session('brandon')
        # test whether sources page opens after user logs in
        sourcePage.driver.get(self.live_server_url)
        sourcePage.sources_button.click()
        git_url = "https://github.com/aaSemble/python-aasemble.django.git"
        sourcePage.create_new_package_source(git_url=git_url, branch='master', series='brandon/aasemble')
        self.assertEqual(sourcePage.verify_package_source(git_url=git_url), True, 'Package not created')
        sourcePage.delete_package_source()
        self.assertEqual(sourcePage.verify_package_source(git_url=git_url), False, 'Package not deleted')

    def test_profile_button(self):
        '''This test verifies the "Profile" button.
            1. Create a session cookie for given user. We are using a existing
               # user 'brandon' which is already added as fixture.
            2. Press 'Profile' button.
            3. Verify page by username'''
        self.create_login_session('brandon')
        profilePage = ProfilePage(self.driver)
        # test whether sources page opens after user logs in
        profilePage.driver.get(self.live_server_url)
        profilePage.profile_button.click()
        self.assertEqual(profilePage.verify_profile_page('brandon'), True, "Profile Name not verified")

    @override_settings(CELERY_ALWAYS_EAGER=True)
    # This tests needs celery so overriding the settings
    def test_build_packages(self):
        '''This test perform a package addtion and check whether a build
         started for the same.
         1. Create a session cookie for given user. We are using a existing
               # user 'brandon' which is already added as fixture.
         2. Try to create a package.
         3. Poll the task for package creation. Polling should start the build
         4. Verify that Building started and it is visible via GUI'''
        sourcePage = SourcePage(self.driver)
        self.create_login_session('brandon')
        # test whether sources page opens after user logs in
        sourcePage.driver.get(self.live_server_url)
        sourcePage.sources_button.click()
        git_url = "https://github.com/aaSemble/python-aasemble.django.git"
        sourcePage.create_new_package_source(git_url=git_url, branch='master', series='brandon/aasemble')
        self.assertEqual(sourcePage.verify_package_source(git_url=git_url), True, 'Package not created')
        from .models import PackageSource
        # Only one package is added with this url
        P = PackageSource.objects.filter(git_url=git_url)[0]
        try:
            poll_one(P.id)
        except:
            # Marking Pass even if we got some exception during package build.
            # Our verification is limited to UI inteface. Form UI, It should
            # be visible (even if it has just started)
            pass
        finally:
            buildPage = BuildPage(self.driver)
            buildPage.driver.get(self.live_server_url)
            buildPage.build_button.click()
            self.assertEqual(buildPage.verify_build_displayed(packageName='python-aasemble.django.git'), True, 'Build not started')

    def test_overview_button(self):
        '''This test performs the test for overview button
          1. Create a session cookie for given user. We are using a existing
               # user 'brandon' which is already added as fixture.
          2. Press 'Overview' button.
          3. Verify whether 'Dashboard' came.'''
        self.create_login_session('brandon')
        overviewPage = OverviewPage(self.driver)
        # test whether sources page opens after user logs in
        overviewPage.driver.get(self.live_server_url)
        overviewPage.overview_button.click()
        pageHeader = overviewPage.get_page_header_value()
        self.assertEqual(pageHeader.text, "Dashboard", "Dashboard didn't showed up")

    def test_logout_button(self):
        '''This test perform a logout from given seesion
        # 1. Create a session cookie for given user. We are using a existing
               # user 'brandon' which is already added as fixture.
        # 2. Press logout.
        # 3. Verify that we came to login page.'''
        self.create_login_session('brandon')
        logoutPage = LogoutPage(self.driver)
        # test whether sources page opens after user logs in
        logoutPage.driver.get(self.live_server_url)
        logoutPage.logout_button.click()
        self.assertEqual(logoutPage.verify_login_page(), True, "Logout didn't work")

    def test_new_mirrors(self):
        ''' This tests validates if non public mirror is created'''
        self.create_login_session('brandon')
        mirrorPage = MirrorPage(self.driver)
        mirrorPage.driver.get(self.live_server_url)
        mirrorPage.mirror_button.click()
        #self.assertTrue(mirrorPage.verify_if_element_visible(("by.By.LINK_TEXT", 'New')), "Mirror New Button is not Visible")
        mirrorPage.new_button.click()
        mirrorPage.url_field.send_keys('%s%s' % (self.live_server_url, '/apt/brandon/brandon'))
        mirrorPage.series_field.send_keys('brandon/aasemble')
        mirrorPage.component_field.send_keys('aasemble')
        mirrorPage.submit_button.click()
        self.assertTrue(mirrorPage.verify_if_element_visible(("by.By.LINK_TEXT", '%s%s' % (self.live_server_url, '/apt/brandon/brandon'))))
        # Test if public flag is false
        self.assertTrue(mirrorPage.verify_if_element_visible(("by.By.XPATH", ".//table/tbody/tr[1]/td[5][contains(text(), False)]")))
