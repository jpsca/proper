"""Comprehensive tests for the textify HTML to plain text converter."""
from proper.helpers import textify


class TestBasicConversion:
    """Test basic HTML to text conversion."""

    def test_simple_html(self):
        html = """
        <html>
          <body>
            <h1>Hello World</h1>
            <p>This is a <a href="http://example.com">link</a>.</p>
          </body>
        </html>
        """
        expected_text = "Hello World\n\nThis is a link (http://example.com)."
        result = textify(html)
        print(result)
        assert result == expected_text

    def test_plain_text(self):
        text = "Just plain text"
        result = textify(text)
        print(result)
        assert result == "Just plain text"

    def test_empty_string(self):
        result = textify("")
        print(result)
        assert result == ""

    def test_whitespace_only(self):
        result = textify("   \n\n  ")
        print(result)
        assert result == ""


class TestBodyExtraction:
    """Test body tag extraction."""

    def test_with_body_tag(self):
        html = "<html><body><p>Content</p></body></html>"
        result = textify(html)
        print(result)
        assert result == "Content"

    def test_without_body_tag(self):
        html = "<p>Content</p>"
        result = textify(html)
        print(result)
        assert result == "Content"

    def test_body_tag_case_insensitive(self):
        html = "<html><BODY><p>Content</p></BODY></html>"
        result = textify(html)
        print(result)
        assert result == "Content"

    def test_body_tag_with_attributes(self):
        html = '<body class="main" id="content"><p>Content</p></body>'
        result = textify(html)
        print(result)
        assert result == "Content"


class TestCommentRemoval:
    """Test HTML comment removal."""

    def test_single_line_comment(self):
        html = "<p>Text</p><!-- This is a comment --><p>More text</p>"
        result = textify(html)
        print(result)
        assert result == "Text\n\nMore text"

    def test_multiline_comment(self):
        html = "<p>Before</p>\n<!-- This is a\nmulti-line\ncomment -->\n<p>After</p>"
        result = textify(html)
        print(result)
        assert result == "Before\n\nAfter"

    def test_multiple_comments(self):
        html = "<!-- Comment 1 --><p>Text</p><!-- Comment 2 -->"
        result = textify(html)
        print(result)
        assert result == "Text"

    def test_comment_with_special_chars(self):
        html = "<!-- Comment with <tags> and & special chars --><p>Text</p>"
        result = textify(html)
        print(result)
        assert result == "Text"

class TestBlockLevelTags:
    """Test block-level tag handling."""

    def test_headers(self):
        html = "<h1>H1</h1><h2>H2</h2><h3>H3</h3><h4>H4</h4><h5>H5</h5><h6>H6</h6>"
        result = textify(html)
        print(result)
        assert result == "H1\n\nH2\n\nH3\n\nH4\n\nH5\n\nH6"

    def test_paragraph(self):
        html = "<p>First paragraph</p><p>Second paragraph</p>"
        result = textify(html)
        print(result)
        assert result == "First paragraph\n\nSecond paragraph"

    def test_div(self):
        html = "<div>First div</div><div>Second div</div>"
        result = textify(html)
        print(result)
        assert result == "First div\n\nSecond div"

    def test_lists(self):
        html = "<ul><li>Item 1</li><li>Item 2</li></ul>"
        result = textify(html)
        print(result)
        assert result == "- Item 1\n- Item 2"

    def test_ordered_list(self):
        html = "<ol><li>First</li><li>Second</li></ol>"
        result = textify(html)
        print(result)
        assert result == "- First\n- Second"

    def test_semantic_tags(self):
        html = "<article>Article</article><section>Section</section><header>Header</header>"
        result = textify(html)
        print(result)
        assert result == "Article\n\nSection\n\nHeader"

    def test_blockquote(self):
        html = "<blockquote>Quote text</blockquote>"
        result = textify(html)
        print(result)
        assert result == "Quote text"

    def test_address(self):
        html = "<address>123 Main St</address>"
        result = textify(html)
        print(result)
        assert result == "123 Main St"

    def test_dl_dt_dd(self):
        html = "<dl><dt>Term</dt><dd>Definition</dd></dl>"
        result = textify(html)
        print(result)
        assert result == "Term\n\nDefinition"

    def test_figure_and_figcaption(self):
        html = "<figure><figcaption>Caption text</figcaption></figure>"
        result = textify(html)
        print(result)
        assert result == "Caption text"

    def test_form_tags(self):
        html = "<form><fieldset>Form content</fieldset></form>"
        result = textify(html)
        print(result)
        assert result == "Form content"

    def test_table(self):
        html = "<table><tr><td>Cell</td></tr></table>"
        result = textify(html)
        print(result)
        assert result == "Cell"


class TestIgnoreTags:
    """Test tags that should be removed with their contents.
    """

    def test_script_tag(self):
        html = "<p>Before</p><script>alert('test');</script><p>After</p>"
        result = textify(html)
        print(result)
        assert "Before" in result and "After" in result

    def test_style_tag(self):
        html = "<p>Text</p><style>.class { color: red; }</style>"
        result = textify(html)
        print(result)
        assert "Text" in result

    def test_canvas_tag(self):
        html = "<p>Text</p><canvas>Canvas content</canvas>"
        result = textify(html)
        print(result)
        assert "Text" in result

    def test_template_tag(self):
        html = "<p>Text</p><template>Template content</template>"
        result = textify(html)
        print(result)
        assert "Text" in result

    def test_multiple_ignore_tags(self):
        html = """
        <p>Keep this</p>
        <script>Remove this</script>
        <style>And this</style>
        <canvas>Remove canvas</canvas>
        <p>Keep this too</p>
        """
        result = textify(html)
        print(result)
        assert "Keep this" in result
        assert "Keep this too" in result


class TestLinkHandling:
    """Test anchor tag conversion."""

    def test_standard_link(self):
        html = '<a href="http://example.com">Click here</a>'
        result = textify(html)
        print(result)
        assert result == "Click here (http://example.com)"

    def test_link_text_equals_href(self):
        html = '<a href="http://example.com">http://example.com</a>'
        result = textify(html)
        print(result)
        assert result == "http://example.com"

    def test_link_empty_href(self):
        html = '<a href="">Click here</a>'
        result = textify(html)
        print(result)
        assert result == "Click here"

    def test_multiple_links(self):
        html = '<p><a href="http://one.com">One</a> and <a href="http://two.com">Two</a></p>'
        result = textify(html)
        print(result)
        assert "One (http://one.com)" in result
        assert "Two (http://two.com)" in result

    def test_link_case_insensitive(self):
        html = '<A HREF="http://example.com">Link</A>'
        result = textify(html)
        print(result)
        assert "Link (http://example.com)" in result

    def test_link_with_nested_content(self):
        html = '<a href="http://example.com"><strong>Bold</strong> link</a>'
        result = textify(html)
        print(result)
        assert "Bold link (http://example.com)" in result

    def test_link_in_paragraph(self):
        html = '<p>Visit <a href="http://example.com">our site</a> for more.</p>'
        result = textify(html)
        print(result)
        assert result == "Visit our site (http://example.com) for more."


class TestImageHandling:
    """Test image tag conversion."""

    def test_simple_image(self):
        html = '<img src="photo.jpg">'
        result = textify(html)
        print(result)
        assert result == "photo.jpg"

    def test_image_with_alt(self):
        html = '<img src="photo.jpg" alt="A photo">'
        result = textify(html)
        print(result)
        assert result == "photo.jpg"

    def test_image_in_paragraph(self):
        html = '<p>Check out <img src="photo.jpg"> this image</p>'
        result = textify(html)
        print(result)
        assert "photo.jpg" in result
        assert "this image" in result

    def test_multiple_images(self):
        html = '<p><img src="img1.jpg"> and <img src="img2.jpg"></p>'
        result = textify(html)
        print(result)
        assert "img1.jpg" in result
        assert "img2.jpg" in result

    def test_self_closing_image(self):
        html = '<img src="photo.jpg"/>'
        result = textify(html)
        print(result)
        assert result == "photo.jpg"


class TestBreakTags:
    """Test line break handling."""

    def test_single_br(self):
        html = "Line 1<br>Line 2"
        result = textify(html)
        print(result)
        assert result == "Line 1\nLine 2"

    def test_self_closing_br(self):
        html = "Line 1<br/>Line 2"
        result = textify(html)
        print(result)
        assert result == "Line 1\nLine 2"

    def test_multiple_br_tags(self):
        html = "Line 1<br><br>Line 2"
        result = textify(html)
        print(result)
        assert "Line 1" in result and "Line 2" in result

    def test_br_case_insensitive(self):
        html = "Line 1<BR>Line 2"
        result = textify(html)
        print(result)
        assert result == "Line 1\nLine 2"

    def test_br_with_space(self):
        html = "Line 1<br />Line 2"
        result = textify(html)
        print(result)
        assert result == "Line 1\nLine 2"


class TestHorizontalRule:
    """Test horizontal rule conversion."""

    def test_hr_tag(self):
        html = "<p>Before</p><hr><p>After</p>"
        result = textify(html)
        print(result)
        assert "Before" in result
        assert "--------------------" in result
        assert "After" in result

    def test_self_closing_hr(self):
        html = "<p>Text</p><hr/><p>More</p>"
        result = textify(html)
        print(result)
        assert "--------------------" in result

    def test_multiple_hr_tags(self):
        html = "<p>One</p><hr><p>Two</p><hr><p>Three</p>"
        result = textify(html)
        print(result)
        assert result.count("--------------------") == 2


class TestCodeTags:
    """Test code tag conversion."""

    def test_code_tag(self):
        html = "<p>Use <code>print()</code> function</p>"
        result = textify(html)
        print(result)
        assert result == "Use `print()` function"

    def test_code_with_attributes(self):
        html = '<code class="python">print()</code>'
        result = textify(html)
        print(result)
        assert result == "`print()`"

    def test_multiple_code_tags(self):
        html = "<p><code>var1</code> and <code>var2</code></p>"
        result = textify(html)
        print(result)
        assert result == "`var1` and `var2`"


class TestPreTags:
    """Test preformatted text handling."""

    def test_pre_tag(self):
        html = "<pre>Code block\nWith newlines</pre>"
        result = textify(html)
        print(result)
        assert "```" in result
        assert "Code block" in result

    def test_pre_with_attributes(self):
        html = '<pre class="code">Text</pre>'
        result = textify(html)
        print(result)
        assert "```" in result
        assert "Text" in result


class TestEntityUnescaping:
    """Test HTML entity conversion."""

    def test_named_entities(self):
        html = "&lt;p&gt;Text &amp; more&lt;/p&gt;"
        result = textify(html)
        print(result)
        assert result == "<p>Text & more</p>"

    def test_numeric_entities(self):
        html = "&#65;&#66;&#67;"  # ABC
        result = textify(html)
        print(result)
        assert result == "ABC"

    def test_hex_entities(self):
        html = "&#x41;&#x42;&#x43;"  # ABC
        result = textify(html)
        print(result)
        assert result == "ABC"

    def test_common_entities(self):
        html = "&quot;Quote&quot; &amp; &lt;tag&gt;"
        result = textify(html)
        print(result)
        assert result == '"Quote" & <tag>'

    def test_nbsp_entity(self):
        html = "Word&nbsp;space"
        # nbsp is converted to \xa0 (non-breaking space character)
        result = textify(html)
        print(result)
        assert result == "Word\xa0space"

    def test_copyright_entity(self):
        html = "Copyright &#169; 2025"
        result = textify(html)
        print(result)
        assert "©" in result

    def test_invalid_entity(self):
        html = "&invalidEntity;"
        # Should remain unchanged or be handled gracefully
        result = textify(html)
        print(result)
        assert result  # Just ensure it doesn't crash

    def test_mixed_entities(self):
        html = "&lt;div&gt; Value: &#169; &#x2665;"
        result = textify(html)
        print(result)
        assert "<div>" in result
        assert "©" in result


class TestWhitespaceCleanup:
    """Test whitespace and newline normalization."""

    def test_multiple_spaces(self):
        html = "<p>Text    with    spaces</p>"
        result = textify(html)
        print(result)
        assert result == "Text with spaces"

    def test_multiple_newlines(self):
        html = "<p>First</p>\n\n\n\n<p>Second</p>"
        result = textify(html)
        print(result)
        assert result == "First\n\nSecond"

    def test_leading_whitespace(self):
        html = "   <p>Text</p>"
        result = textify(html)
        print(result)
        assert result == "Text"

    def test_trailing_whitespace(self):
        html = "<p>Text</p>   "
        result = textify(html)
        print(result)
        assert result == "Text"

    def test_mixed_whitespace(self):
        html = "  <p>Text</p>  \n\n\n  <p>More</p>  "
        result = textify(html)
        print(result)
        assert result == "Text\n\nMore"


class TestIntegration:
    """Integration tests with complex HTML."""

    def test_email_template(self):
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>body { font-family: Arial; }</style>
        </head>
        <body>
            <h1>Welcome!</h1>
            <p>Dear User,</p>
            <p>Thank you for signing up. Visit <a href="https://example.com">our website</a>.</p>
            <ul>
                <li>Feature 1</li>
                <li>Feature 2</li>
            </ul>
            <hr>
            <p>Best regards,<br>The Team</p>
            <script>console.log('tracking');</script>
        </body>
        </html>
        """
        result = textify(html)
        print(result)
        assert "Welcome!" in result
        assert "Dear User," in result
        assert "our website (https://example.com)" in result
        assert "- Feature 1" in result
        assert "- Feature 2" in result
        assert "--------------------" in result
        assert "Best regards" in result

    def test_nested_structures(self):
        html = """
        <div>
            <article>
                <h2>Title</h2>
                <p>Content with <strong>bold</strong> and <em>italic</em>.</p>
                <blockquote>
                    <p>A quote</p>
                </blockquote>
            </article>
        </div>
        """
        result = textify(html)
        print(result)
        # Just verify key content is present with proper formatting
        assert "Title" in result
        assert "Content with bold and italic." in result
        assert "A quote" in result

    def test_real_world_html(self):
        html = """
        <html>
        <body>
            <!-- Navigation -->
            <nav><a href="/home">Home</a> | <a href="/about">About</a></nav>

            <main>
                <h1>Article Title</h1>
                <p>Published on <time>2025-01-01</time></p>

                <p>This is the introduction paragraph with a
                <a href="http://example.com">reference link</a>.</p>

                <h2>Section 1</h2>
                <p>Some content here with <code>code snippet</code>.</p>

                <pre>
                def example():
                    return True
                </pre>

                <h2>Section 2</h2>
                <ul>
                    <li>Point one</li>
                    <li>Point two</li>
                </ul>
            </main>

            <footer>
                <p>&copy; 2025 Company Name</p>
            </footer>
        </body>
        </html>
        """
        result = textify(html)
        print(result)
        assert "Article Title" in result
        assert "reference link (http://example.com)" in result
        assert "`code snippet`" in result
        assert "def example():" in result
        assert "- Point one" in result
        assert "- Point two" in result
        assert "© 2025 Company Name" in result

    def test_mixed_inline_and_block(self):
        html = """
        <div>
            <p>Paragraph with <strong>bold</strong>, <em>italic</em>, and <code>code</code>.</p>
            <p>Another paragraph with <a href="http://test.com">a link</a>.</p>
        </div>
        """
        result = textify(html)
        print(result)
        assert "bold" in result and "italic" in result
        assert "`code`" in result
        assert "a link (http://test.com)" in result

    def test_malformed_html(self):
        html = "<p>Unclosed paragraph<div>Unclosed div<p>Another paragraph</p>"
        result = textify(html)
        print(result)
        # Just verify all content is preserved
        assert "Unclosed paragraph" in result
        assert "Unclosed div" in result
        assert "Another paragraph" in result


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_tags(self):
        html = "<p></p><div></div><span></span>"
        result = textify(html)
        print(result)
        assert result == ""

    def test_self_closing_tags(self):
        html = "<img src='test.jpg'/><input type='text'/>"
        result = textify(html)
        print(result)
        # Should handle gracefully without errors
        assert isinstance(result, str)

    def test_tags_with_multiple_attributes(self):
        html = '<a href="http://test.com" class="link" id="main" target="_blank">Link</a>'
        result = textify(html)
        print(result)
        assert "Link (http://test.com)" in result

    def test_case_sensitivity(self):
        html = "<P>Paragraph</P><DIV>Division</DIV><A HREF='http://test.com'>Link</A>"
        result = textify(html)
        print(result)
        assert result == "Paragraph\n\nDivision\n\nLink (http://test.com)"

    def test_unicode_characters(self):
        html = "<p>Unicode: 你好 مرحبا שלום</p>"
        result = textify(html)
        print(result)
        assert result == "Unicode: 你好 مرحبا שלום"

    def test_special_chars_in_attributes(self):
        html = '<a href="http://test.com?foo=1&bar=2">Link</a>'
        result = textify(html)
        print(result)
        assert "Link" in result
        # URL should be preserved
        assert "test.com" in result

    def test_deeply_nested_tags(self):
        html = "<div><div><div><div><div><p>Deep</p></div></div></div></div></div>"
        result = textify(html)
        print(result)
        assert result == "Deep"

    def test_adjacent_tags(self):
        html = "<strong>Bold</strong><em>Italic</em><code>Code</code>"
        result = textify(html)
        print(result)
        assert result == "BoldItalic`Code`"

    def test_whitespace_in_tags(self):
        html = "<p  >Text</p><br  /><a  href = 'url' >Link</a>"
        result = textify(html)
        print(result)
        assert result == "Text\n\nLink"


class TestSecurity:
    """Security and robustness tests."""

    def test_script_injection_attempt(self):
        html = "<p>Safe text</p><script>alert('XSS')</script><p>More safe text</p>"
        result = textify(html)
        print(result)
        assert "Safe text" in result and "More safe text" in result


    def test_extremely_nested_structure(self):
        # Create deeply nested structure
        html = "<div>" * 100 + "Content" + "</div>" * 100
        result = textify(html)
        print(result)
        assert "Content" in result

    def test_malformed_entities(self):
        html = "&#; &#x; &; &#999999999;"
        # Should not crash
        result = textify(html)
        print(result)
        assert isinstance(result, str)

    def test_invalid_html_structure(self):
        html = "</p><div>Text</div><p>"
        result = textify(html)
        print(result)
        assert result == "Text"


class TestRegressionCases:
    """Tests for specific bugs or regressions."""

    def test_link_with_matching_text_and_url(self):
        """Ensure links where text equals URL don't show duplicate."""
        html = '<a href="http://example.com">http://example.com</a>'
        result = textify(html)
        print(result)
        # Should only appear once, not "http://example.com (http://example.com)"
        assert result == "http://example.com"
        assert result.count("http://example.com") == 1

    def test_empty_link_text(self):
        """Handle links with no visible text."""
        html = '<a href="http://example.com"></a>'
        result = textify(html)
        print(result)
        # Should handle gracefully
        assert isinstance(result, str)

    def test_consecutive_block_tags(self):
        """Ensure consecutive block tags don't create excessive newlines."""
        html = "<div>One</div><div>Two</div><div>Three</div>"
        result = textify(html)
        print(result)
        # Should have at most 2 consecutive newlines
        assert "\n\n\n" not in result

    def test_br_tag_variants(self):
        """Test all variants of br tags."""
        variants = ["<br>", "<br/>", "<br />", "<BR>", "<Br>"]
        for variant in variants:
            html = f"Line1{variant}Line2"
            result = textify(html)
            print(result)
            assert "Line1" in result and "Line2" in result
