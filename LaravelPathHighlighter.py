import sublime
import sublime_plugin
import threading
import re

class LaravelPathHighlighter(sublime_plugin.EventListener):

	URL_REGEX = "\\b([a-z]+)::([a-zA-Z\.\-]+)"
	DEFAULT_MAX_URLS = 200
	SETTINGS_FILENAME = 'LaravelPowerup.sublime-settings'

	urls_for_view = {}
	scopes_for_view = {}
	ignored_views = []
	highlight_semaphore = threading.Semaphore()

	def on_activated(self, view):
		self.update_url_highlights(view)

	# Async listeners
	def on_load_async(self, view):
		self.update_url_highlights_async(view)

	def on_modified_async(self, view):
		self.update_url_highlights_async(view)

	def on_close(self, view):
		for map in [self.urls_for_view, self.scopes_for_view, self.ignored_views]:
			if view.id() in map:
				del map[view.id()]

	"""The logic entry point. Find all URLs in view, store and highlight them"""
	def update_url_highlights(self, view):
		settings = sublime.load_settings(LaravelPathHighlighter.SETTINGS_FILENAME)
		should_highlight_urls = settings.get('highlight_urls', True)
		max_url_limit = settings.get('max_url_limit', LaravelPathHighlighter.DEFAULT_MAX_URLS)

		if view.id() in LaravelPathHighlighter.ignored_views:
			return

		urls = view.find_all(LaravelPathHighlighter.URL_REGEX)
		#print(urls)

		# Avoid slowdowns for views with too much URLs
		if len(urls) > max_url_limit:
			print("LaravelPathHighlighter: ignoring view with %u URLs" % len(urls))
			LaravelPathHighlighter.ignored_views.append(view.id())
			return

		LaravelPathHighlighter.urls_for_view[view.id()] = urls

		should_highlight_urls = sublime.load_settings(LaravelPathHighlighter.SETTINGS_FILENAME).get('highlight_urls', True)
		if (should_highlight_urls):
			self.highlight_urls(view, urls)

	"""Same as update_url_highlights, but avoids race conditions with a semaphore."""
	def update_url_highlights_async(self, view):
		LaravelPathHighlighter.highlight_semaphore.acquire()
		try:
			self.update_url_highlights(view)
		finally:
			LaravelPathHighlighter.highlight_semaphore.release()

	"""Creates a set of regions from the intersection of urls and scopes, underlines all of them."""
	def highlight_urls(self, view, urls):
		# We need separate regions for each lexical scope for ST to use a proper color for the underline
		scope_map = {}
		for url in urls:
			scope_name = view.scope_name(url.a)
			scope_map.setdefault(scope_name, []).append(url)

		for scope_name in scope_map:
			self.underline_regions(view, scope_name, scope_map[scope_name])

		self.update_view_scopes(view, scope_map.keys())

	"""Apply underlining with provided scope name to provided regions."""
	def underline_regions(self, view, scope_name, regions):
		view.add_regions(
			u'clickable-urls ' + scope_name,
			regions,
			scope_name,
			flags=sublime.DRAW_NO_FILL|sublime.DRAW_NO_OUTLINE|sublime.DRAW_STIPPLED_UNDERLINE)

	"""Store new set of underlined scopes for view. Erase underlining from
	scopes that were used but are not anymore."""
	def update_view_scopes(self, view, new_scopes):
		old_scopes = LaravelPathHighlighter.scopes_for_view.get(view.id(), None)
		if old_scopes:
			unused_scopes = set(old_scopes) - set(new_scopes)
			for unused_scope_name in unused_scopes:
				view.erase_regions(u'clickable-urls ' + unused_scope_name)

		LaravelPathHighlighter.scopes_for_view[view.id()] = new_scopes



def open_url(url):
	print('Click on Laravel Path: ' + url)
	url = re.sub(r"[:.-]", '', url)
	pattern = '*' + url
	print('Try finding file(s) with pattern: ' + pattern)
	path = sublime.find_resources(pattern)
	if (len(path) == 1):
		sublime.active_window().open_file(path[0])
	else:
		sublime.active_window().run_command("show_overlay", {"overlay": "goto", "text": url})

class OpenLaravelPathUnderCursorCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		if self.view.id() in LaravelPathHighlighter.urls_for_view:
			selection = self.view.sel()[0]
			if selection.empty():
				selection = next((url for url in LaravelPathHighlighter.urls_for_view[self.view.id()] if url.contains(selection)), None)
				if not selection:
					return
			url = self.view.substr(selection)
			open_url(url)
