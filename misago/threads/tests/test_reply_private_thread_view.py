from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from ...attachments.enums import AllowedAttachments
from ...attachments.models import Attachment
from ...conf.test import override_dynamic_settings
from ...permissions.enums import CanUploadAttachments
from ...posting.forms import PostForm
from ...posting.formsets import PostingFormset
from ...readtracker.models import ReadCategory
from ...readtracker.tracker import mark_thread_read
from ...test import (
    assert_contains,
    assert_contains_element,
    assert_not_contains,
)
from ..test import reply_thread


def test_reply_private_thread_view_displays_login_page_to_guests(
    client, other_user_private_thread
):
    response = client.get(
        reverse(
            "misago:reply-private-thread",
            kwargs={
                "id": other_user_private_thread.id,
                "slug": other_user_private_thread.slug,
            },
        )
    )
    assert_contains(response, "Sign in to reply to threads")


def test_reply_private_thread_view_displays_error_page_to_users_without_private_threads_permission(
    user, user_client, other_user_private_thread
):
    user.group.can_use_private_threads = False
    user.group.save()

    response = user_client.get(
        reverse(
            "misago:reply-private-thread",
            kwargs={
                "id": other_user_private_thread.id,
                "slug": other_user_private_thread.slug,
            },
        )
    )
    assert_contains(
        response,
        "You can&#x27;t use private threads.",
        status_code=403,
    )


def test_reply_private_thread_view_displays_error_page_to_user_who_cant_see_private_thread(
    user_client, private_thread
):
    response = user_client.get(
        reverse(
            "misago:reply-private-thread",
            kwargs={"id": private_thread.id, "slug": private_thread.slug},
        )
    )
    assert response.status_code == 404


def test_reply_private_thread_view_displays_reply_thread_form(
    user_client, other_user_private_thread
):
    response = user_client.get(
        reverse(
            "misago:reply-private-thread",
            kwargs={
                "id": other_user_private_thread.id,
                "slug": other_user_private_thread.slug,
            },
        )
    )
    assert_contains(response, "Reply to thread")


def test_reply_private_thread_view_posts_new_thread_reply(
    user_client, other_user_private_thread
):
    response = user_client.post(
        reverse(
            "misago:reply-private-thread",
            kwargs={
                "id": other_user_private_thread.id,
                "slug": other_user_private_thread.slug,
            },
        ),
        {
            "posting-post-post": "Reply contents",
        },
    )
    assert response.status_code == 302

    other_user_private_thread.refresh_from_db()
    assert (
        response["location"]
        == reverse(
            "misago:private-thread",
            kwargs={
                "id": other_user_private_thread.pk,
                "slug": other_user_private_thread.slug,
            },
        )
        + f"#post-{other_user_private_thread.last_post_id}"
    )


def test_reply_private_thread_view_posts_new_thread_reply_in_htmx(
    user_client, other_user_private_thread
):
    response = user_client.post(
        reverse(
            "misago:reply-private-thread",
            kwargs={
                "id": other_user_private_thread.id,
                "slug": other_user_private_thread.slug,
            },
        ),
        {
            "posting-post-post": "Reply contents",
        },
        headers={"hx-request": "true"},
    )
    assert response.status_code == 204

    other_user_private_thread.refresh_from_db()
    assert (
        response["hx-redirect"]
        == reverse(
            "misago:private-thread",
            kwargs={
                "id": other_user_private_thread.pk,
                "slug": other_user_private_thread.slug,
            },
        )
        + f"#post-{other_user_private_thread.last_post_id}"
    )


def test_reply_private_thread_view_posts_new_thread_reply_in_quick_reply(
    user_client, other_user_private_thread
):
    response = user_client.post(
        reverse(
            "misago:reply-private-thread",
            kwargs={
                "id": other_user_private_thread.id,
                "slug": other_user_private_thread.slug,
            },
        ),
        {
            "posting-post-post": "Reply contents",
            "quick_reply": "true",
        },
    )
    assert response.status_code == 302

    other_user_private_thread.refresh_from_db()
    assert (
        response["location"]
        == reverse(
            "misago:private-thread",
            kwargs={
                "id": other_user_private_thread.pk,
                "slug": other_user_private_thread.slug,
            },
        )
        + f"#post-{other_user_private_thread.last_post_id}"
    )


def test_reply_private_thread_view_posts_new_thread_reply_in_quick_reply_with_htmx(
    user_client, other_user_private_thread
):
    response = user_client.post(
        reverse(
            "misago:reply-private-thread",
            kwargs={
                "id": other_user_private_thread.id,
                "slug": other_user_private_thread.slug,
            },
        ),
        {
            "posting-post-post": "Reply contents",
            "quick_reply": "true",
        },
        headers={"hx-request": "true"},
    )
    assert response.status_code == 200

    other_user_private_thread.refresh_from_db()
    assert_contains(response, f"post-{other_user_private_thread.last_post_id}")
    assert_contains(response, f"<p>Reply contents</p>")


def test_reply_private_thread_view_posted_reply_in_quick_reply_with_htmx_is_read(
    user, user_client, other_user_private_thread
):
    mark_thread_read(
        user, other_user_private_thread, other_user_private_thread.last_post.posted_on
    )

    response = user_client.post(
        reverse(
            "misago:reply-private-thread",
            kwargs={
                "id": other_user_private_thread.id,
                "slug": other_user_private_thread.slug,
            },
        ),
        {
            "posting-post-post": "Reply contents",
            "quick_reply": "true",
        },
        headers={"hx-request": "true"},
    )
    assert response.status_code == 200

    other_user_private_thread.refresh_from_db()
    assert_contains(response, f"post-{other_user_private_thread.last_post_id}")
    assert_contains(response, f"<p>Reply contents</p>")

    ReadCategory.objects.get(
        user=user,
        category=other_user_private_thread.category,
        read_time=other_user_private_thread.last_post_on,
    )


def test_reply_private_thread_view_previews_message(
    user_client, other_user_private_thread
):
    response = user_client.post(
        reverse(
            "misago:reply-private-thread",
            kwargs={
                "id": other_user_private_thread.id,
                "slug": other_user_private_thread.slug,
            },
        ),
        {
            PostingFormset.preview_action: "true",
            "posting-post-post": "Reply contents",
        },
    )
    assert_contains(response, "Reply to thread")
    assert_contains(response, "Message preview")


def test_reply_private_thread_view_previews_message_in_htmx(
    user_client, other_user_private_thread
):
    response = user_client.post(
        reverse(
            "misago:reply-private-thread",
            kwargs={
                "id": other_user_private_thread.id,
                "slug": other_user_private_thread.slug,
            },
        ),
        {
            PostingFormset.preview_action: "true",
            "posting-post-post": "Reply contents",
        },
        headers={"hx-request": "true"},
    )
    assert_contains(response, "Reply to thread")
    assert_contains(response, "Message preview")


def test_reply_private_thread_view_previews_message_in_quick_reply(
    user_client, other_user_private_thread
):
    response = user_client.post(
        reverse(
            "misago:reply-private-thread",
            kwargs={
                "id": other_user_private_thread.id,
                "slug": other_user_private_thread.slug,
            },
        ),
        {
            PostingFormset.preview_action: "true",
            "posting-post-post": "Reply contents",
            "quick_reply": "true",
        },
    )
    assert_contains(response, "Post reply")
    assert_contains(response, "Message preview")


def test_reply_private_thread_view_previews_message_in_quick_reply_with_htmx(
    user_client, other_user_private_thread
):
    response = user_client.post(
        reverse(
            "misago:reply-private-thread",
            kwargs={
                "id": other_user_private_thread.id,
                "slug": other_user_private_thread.slug,
            },
        ),
        {
            PostingFormset.preview_action: "true",
            "posting-post-post": "Reply contents",
            "quick_reply": "true",
        },
        headers={"hx-request": "true"},
    )
    assert_contains(response, "Post reply")
    assert_contains(response, "Message preview")


def test_reply_private_thread_view_validates_post(
    user_client, other_user_private_thread
):
    response = user_client.post(
        reverse(
            "misago:reply-private-thread",
            kwargs={
                "id": other_user_private_thread.id,
                "slug": other_user_private_thread.slug,
            },
        ),
        {
            "posting-post-post": "?",
        },
    )
    assert_contains(response, "Post reply")
    assert_contains(
        response, "Posted message must be at least 5 characters long (it has 1)."
    )


def test_reply_private_thread_view_validates_posted_contents(
    user_client, other_user_private_thread, posted_contents_validator
):
    response = user_client.post(
        reverse(
            "misago:reply-private-thread",
            kwargs={
                "id": other_user_private_thread.id,
                "slug": other_user_private_thread.slug,
            },
        ),
        {
            "posting-post-post": "This is a spam message",
        },
    )
    assert_contains(response, "Post reply")
    assert_contains(response, "Your message contains spam!")


@override_dynamic_settings(merge_concurrent_posts=0)
def test_reply_private_thread_view_runs_flood_control(
    user_client, other_user_private_thread, user_reply
):
    response = user_client.post(
        reverse(
            "misago:reply-private-thread",
            kwargs={
                "id": other_user_private_thread.id,
                "slug": other_user_private_thread.slug,
            },
        ),
        {
            "posting-post-post": "This is a flood message",
        },
    )
    assert_contains(response, "Post reply")
    assert_contains(
        response, "You can&#x27;t post a new message so soon after the previous one."
    )


def test_reply_private_thread_view_appends_reply_to_user_recent_post(
    user, user_client, other_user_private_thread
):
    reply = reply_thread(other_user_private_thread, user, message="Previous message")

    response = user_client.post(
        reverse(
            "misago:reply-private-thread",
            kwargs={
                "id": other_user_private_thread.id,
                "slug": other_user_private_thread.slug,
            },
        ),
        {
            "posting-post-post": "Reply contents",
        },
    )
    assert response.status_code == 302

    other_user_private_thread.refresh_from_db()
    assert (
        response["location"]
        == reverse(
            "misago:private-thread",
            kwargs={
                "id": other_user_private_thread.pk,
                "slug": other_user_private_thread.slug,
            },
        )
        + f"#post-{reply.id}"
    )

    reply.refresh_from_db()
    assert reply.original == "Previous message\n\nReply contents"


def test_reply_private_thread_view_appends_reply_to_user_recent_post_in_quick_reply_with_htmx(
    user, user_client, other_user_private_thread
):
    reply = reply_thread(other_user_private_thread, user, message="Previous message")

    response = user_client.post(
        reverse(
            "misago:reply-private-thread",
            kwargs={
                "id": other_user_private_thread.id,
                "slug": other_user_private_thread.slug,
            },
        ),
        {
            "posting-post-post": "Reply contents",
            "quick_reply": "true",
        },
        headers={"hx-request": "true"},
    )
    assert response.status_code == 200

    assert_contains(response, f"post-{reply.id}")
    assert_contains(response, reply.parsed)

    reply.refresh_from_db()
    assert reply.original == "Previous message\n\nReply contents"


@override_dynamic_settings(merge_concurrent_posts=0, flood_control=0)
def test_reply_private_thread_view_doesnt_append_reply_to_user_recent_post_if_feature_is_disabled(
    user, user_client, other_user_private_thread
):
    reply = reply_thread(other_user_private_thread, user, message="Previous message")

    response = user_client.post(
        reverse(
            "misago:reply-private-thread",
            kwargs={
                "id": other_user_private_thread.id,
                "slug": other_user_private_thread.slug,
            },
        ),
        {
            "posting-post-post": "Reply contents",
        },
    )
    assert response.status_code == 302

    other_user_private_thread.refresh_from_db()
    assert (
        response["location"]
        == reverse(
            "misago:private-thread",
            kwargs={
                "id": other_user_private_thread.pk,
                "slug": other_user_private_thread.slug,
            },
        )
        + f"#post-{other_user_private_thread.last_post_id}"
    )

    reply.refresh_from_db()
    assert reply.original == "Previous message"
    assert other_user_private_thread.last_post_id > reply.id


@override_dynamic_settings(flood_control=0)
def test_reply_private_thread_view_doesnt_append_reply_to_user_recent_post_in_preview(
    user, user_client, other_user_private_thread
):
    reply_thread(other_user_private_thread, user, message="Previous message")

    response = user_client.post(
        reverse(
            "misago:reply-private-thread",
            kwargs={
                "id": other_user_private_thread.id,
                "slug": other_user_private_thread.slug,
            },
        ),
        {
            PostingFormset.preview_action: "true",
            "posting-post-post": "Reply contents",
        },
    )
    assert response.status_code == 200
    assert_contains(response, "<p>Reply contents</p>")
    assert_not_contains(response, "<p>Previous message</p>")


@override_dynamic_settings(merge_concurrent_posts=1)
def test_reply_private_thread_view_doesnt_append_reply_to_user_recent_post_if_recent_post_is_too_old(
    user, user_client, other_user_private_thread
):
    reply = reply_thread(
        other_user_private_thread,
        user,
        message="Previous message",
        posted_on=timezone.now() - timedelta(minutes=2),
    )

    response = user_client.post(
        reverse(
            "misago:reply-private-thread",
            kwargs={
                "id": other_user_private_thread.id,
                "slug": other_user_private_thread.slug,
            },
        ),
        {
            "posting-post-post": "Reply contents",
        },
    )
    assert response.status_code == 302

    other_user_private_thread.refresh_from_db()
    assert (
        response["location"]
        == reverse(
            "misago:private-thread",
            kwargs={
                "id": other_user_private_thread.pk,
                "slug": other_user_private_thread.slug,
            },
        )
        + f"#post-{other_user_private_thread.last_post_id}"
    )

    reply.refresh_from_db()
    assert reply.original == "Previous message"
    assert other_user_private_thread.last_post_id > reply.id


@override_dynamic_settings(flood_control=0)
def test_reply_private_thread_view_doesnt_append_reply_to_user_recent_post_if_recent_post_is_by_other_user(
    other_user, user_client, other_user_private_thread
):
    reply = reply_thread(
        other_user_private_thread, other_user, message="Previous message"
    )

    response = user_client.post(
        reverse(
            "misago:reply-private-thread",
            kwargs={
                "id": other_user_private_thread.id,
                "slug": other_user_private_thread.slug,
            },
        ),
        {
            "posting-post-post": "Reply contents",
        },
    )
    assert response.status_code == 302

    other_user_private_thread.refresh_from_db()
    assert (
        response["location"]
        == reverse(
            "misago:private-thread",
            kwargs={
                "id": other_user_private_thread.pk,
                "slug": other_user_private_thread.slug,
            },
        )
        + f"#post-{other_user_private_thread.last_post_id}"
    )

    reply.refresh_from_db()
    assert reply.original == "Previous message"
    assert other_user_private_thread.last_post_id > reply.id


@override_dynamic_settings(flood_control=0)
def test_reply_private_thread_view_doesnt_append_reply_to_user_recent_post_if_recent_post_is_hidden(
    user, user_client, other_user_private_thread
):
    reply = reply_thread(
        other_user_private_thread,
        user,
        message="Previous message",
        is_hidden=True,
    )

    response = user_client.post(
        reverse(
            "misago:reply-private-thread",
            kwargs={
                "id": other_user_private_thread.id,
                "slug": other_user_private_thread.slug,
            },
        ),
        {
            "posting-post-post": "Reply contents",
        },
    )
    assert response.status_code == 302

    other_user_private_thread.refresh_from_db()
    assert (
        response["location"]
        == reverse(
            "misago:private-thread",
            kwargs={
                "id": other_user_private_thread.pk,
                "slug": other_user_private_thread.slug,
            },
        )
        + f"#post-{other_user_private_thread.last_post_id}"
    )

    reply.refresh_from_db()
    assert reply.original == "Previous message"
    assert other_user_private_thread.last_post_id > reply.id


@override_dynamic_settings(flood_control=0)
def test_reply_private_thread_view_doesnt_append_reply_to_user_recent_post_if_recent_post_is_not_editable(
    user, user_client, other_user_private_thread
):
    reply = reply_thread(
        other_user_private_thread,
        user,
        message="Previous message",
        is_protected=True,
    )

    response = user_client.post(
        reverse(
            "misago:reply-private-thread",
            kwargs={
                "id": other_user_private_thread.id,
                "slug": other_user_private_thread.slug,
            },
        ),
        {
            "posting-post-post": "Reply contents",
        },
    )
    assert response.status_code == 302

    other_user_private_thread.refresh_from_db()
    assert (
        response["location"]
        == reverse(
            "misago:private-thread",
            kwargs={
                "id": other_user_private_thread.pk,
                "slug": other_user_private_thread.slug,
            },
        )
        + f"#post-{other_user_private_thread.last_post_id}"
    )

    reply.refresh_from_db()
    assert reply.original == "Previous message"
    assert other_user_private_thread.last_post_id > reply.id


def test_reply_private_thread_view_shows_error_if_thread_is_accessed(
    user_client, thread
):
    response = user_client.get(
        reverse(
            "misago:reply-private-thread",
            kwargs={"id": thread.id, "slug": thread.slug},
        ),
    )

    assert_not_contains(response, "Reply to thread", status_code=404)
    assert_not_contains(response, thread.title, status_code=404)


def test_reply_private_thread_view_displays_attachments_form(
    user_client, other_user_private_thread
):
    response = user_client.get(
        reverse(
            "misago:reply-private-thread",
            kwargs={
                "id": other_user_private_thread.id,
                "slug": other_user_private_thread.slug,
            },
        ),
    )
    assert_contains(response, "Reply to thread")
    assert_contains(response, "misago-editor-attachments=")


@override_dynamic_settings(allowed_attachment_types=AllowedAttachments.NONE.value)
def test_reply_private_thread_view_hides_attachments_form_if_uploads_are_disabled(
    user_client, other_user_private_thread
):
    response = user_client.get(
        reverse(
            "misago:reply-private-thread",
            kwargs={
                "id": other_user_private_thread.id,
                "slug": other_user_private_thread.slug,
            },
        ),
    )
    assert_contains(response, "Reply to thread")
    assert_not_contains(response, "misago-editor-attachments=")


def test_reply_private_thread_view_hides_attachments_form_if_user_has_no_group_permission(
    members_group, user_client, other_user_private_thread
):
    members_group.can_upload_attachments = CanUploadAttachments.THREADS
    members_group.save()

    response = user_client.get(
        reverse(
            "misago:reply-private-thread",
            kwargs={
                "id": other_user_private_thread.id,
                "slug": other_user_private_thread.slug,
            },
        ),
    )
    assert_contains(response, "Reply to thread")
    assert_not_contains(response, "misago-editor-attachments=")


def test_reply_private_thread_view_uploads_attachment_on_submit(
    user, user_client, other_user_private_thread, teardown_attachments
):
    assert not Attachment.objects.exists()

    response = user_client.post(
        reverse(
            "misago:reply-private-thread",
            kwargs={
                "id": other_user_private_thread.id,
                "slug": other_user_private_thread.slug,
            },
        ),
        {
            "posting-post-post": "Reply contents",
            "posting-post-upload": [
                SimpleUploadedFile("test.txt", b"Hello world!", "text/plain"),
            ],
        },
    )
    assert response.status_code == 302

    other_user_private_thread.refresh_from_db()

    attachment = Attachment.objects.get(uploader=user)
    assert attachment.category_id == other_user_private_thread.category_id
    assert attachment.thread_id == other_user_private_thread.id
    assert attachment.post_id == other_user_private_thread.last_post_id
    assert attachment.uploader_id == user.id
    assert not attachment.is_deleted
    assert attachment.name == "test.txt"


@pytest.mark.parametrize(
    "action_name", (PostingFormset.preview_action, PostForm.upload_action)
)
def test_reply_private_thread_view_uploads_attachment_on_preview_or_upload(
    action_name, user, user_client, other_user_private_thread, teardown_attachments
):
    assert not Attachment.objects.exists()

    response = user_client.post(
        reverse(
            "misago:reply-private-thread",
            kwargs={
                "id": other_user_private_thread.id,
                "slug": other_user_private_thread.slug,
            },
        ),
        {
            action_name: "true",
            "posting-post-post": "Reply contents",
            "posting-post-upload": [
                SimpleUploadedFile("test.txt", b"Hello world!", "text/plain"),
            ],
        },
    )
    assert_contains(response, "Reply to thread")
    assert_contains(response, "misago-editor-attachments=")

    attachment = Attachment.objects.get(uploader=user)
    assert attachment.category_id is None
    assert attachment.thread_id is None
    assert attachment.post_id is None
    assert attachment.uploader_id == user.id
    assert not attachment.is_deleted
    assert attachment.name == "test.txt"

    assert_contains(response, attachment.name)
    assert_contains_element(
        response,
        "input",
        type="hidden",
        name=PostForm.attachment_ids_field,
        value=attachment.id,
    )


@pytest.mark.parametrize(
    "action_name", (PostingFormset.preview_action, PostForm.upload_action)
)
def test_reply_private_thread_view_displays_image_attachment(
    action_name, user_client, other_user_private_thread, user_image_attachment
):
    response = user_client.post(
        reverse(
            "misago:reply-private-thread",
            kwargs={
                "id": other_user_private_thread.id,
                "slug": other_user_private_thread.slug,
            },
        ),
        {
            action_name: "true",
            PostForm.attachment_ids_field: [str(user_image_attachment.id)],
            "posting-post-post": "Reply contents",
        },
    )
    assert_contains(response, "Reply to thread")
    assert_contains(response, "misago-editor-attachments=")

    assert_contains(response, user_image_attachment.name)
    assert_contains(response, user_image_attachment.get_absolute_url())
    assert_contains_element(
        response,
        "input",
        type="hidden",
        name=PostForm.attachment_ids_field,
        value=user_image_attachment.id,
    )


@pytest.mark.parametrize(
    "action_name", (PostingFormset.preview_action, PostForm.upload_action)
)
def test_reply_private_thread_view_displays_image_with_thumbnail_attachment(
    action_name, user_client, other_user_private_thread, user_image_thumbnail_attachment
):
    response = user_client.post(
        reverse(
            "misago:reply-private-thread",
            kwargs={
                "id": other_user_private_thread.id,
                "slug": other_user_private_thread.slug,
            },
        ),
        {
            action_name: "true",
            PostForm.attachment_ids_field: [str(user_image_thumbnail_attachment.id)],
            "posting-post-post": "Reply contents",
        },
    )
    assert_contains(response, "Reply to thread")
    assert_contains(response, "misago-editor-attachments=")

    assert_contains(response, user_image_thumbnail_attachment.name)
    assert_contains(response, user_image_thumbnail_attachment.get_thumbnail_url())
    assert_contains_element(
        response,
        "input",
        type="hidden",
        name=PostForm.attachment_ids_field,
        value=user_image_thumbnail_attachment.id,
    )


@pytest.mark.parametrize(
    "action_name", (PostingFormset.preview_action, PostForm.upload_action)
)
def test_reply_private_thread_view_displays_video_attachment(
    action_name, user_client, other_user_private_thread, user_video_attachment
):
    response = user_client.post(
        reverse(
            "misago:reply-private-thread",
            kwargs={
                "id": other_user_private_thread.id,
                "slug": other_user_private_thread.slug,
            },
        ),
        {
            action_name: "true",
            PostForm.attachment_ids_field: [str(user_video_attachment.id)],
            "posting-post-post": "Reply contents",
        },
    )
    assert_contains(response, "Reply to thread")
    assert_contains(response, "misago-editor-attachments=")

    assert_contains(response, user_video_attachment.name)
    assert_contains(response, user_video_attachment.get_absolute_url())
    assert_contains_element(
        response,
        "input",
        type="hidden",
        name=PostForm.attachment_ids_field,
        value=user_video_attachment.id,
    )


@pytest.mark.parametrize(
    "action_name", (PostingFormset.preview_action, PostForm.upload_action)
)
def test_reply_private_thread_view_displays_file_attachment(
    action_name, user_client, other_user_private_thread, user_text_attachment
):
    response = user_client.post(
        reverse(
            "misago:reply-private-thread",
            kwargs={
                "id": other_user_private_thread.id,
                "slug": other_user_private_thread.slug,
            },
        ),
        {
            action_name: "true",
            PostForm.attachment_ids_field: [str(user_text_attachment.id)],
            "posting-post-post": "Reply contents",
        },
    )
    assert_contains(response, "Reply to thread")
    assert_contains(response, "misago-editor-attachments=")

    assert_contains(response, user_text_attachment.name)
    assert_contains_element(
        response,
        "input",
        type="hidden",
        name=PostForm.attachment_ids_field,
        value=user_text_attachment.id,
    )


def test_reply_private_thread_view_associates_unused_attachment_on_submit(
    user_client, other_user_private_thread, user_text_attachment
):
    response = user_client.post(
        reverse(
            "misago:reply-private-thread",
            kwargs={
                "id": other_user_private_thread.id,
                "slug": other_user_private_thread.slug,
            },
        ),
        {
            PostForm.attachment_ids_field: [str(user_text_attachment.id)],
            "posting-post-post": "Reply contents",
        },
    )
    assert response.status_code == 302

    other_user_private_thread.refresh_from_db()

    user_text_attachment.refresh_from_db()
    assert user_text_attachment.category_id == other_user_private_thread.category_id
    assert user_text_attachment.thread_id == other_user_private_thread.id
    assert user_text_attachment.post_id == other_user_private_thread.last_post_id
    assert not user_text_attachment.is_deleted


def test_reply_private_thread_view_adds_attachment_to_deleted_list(
    user_client, other_user_private_thread, user_text_attachment
):
    response = user_client.post(
        reverse(
            "misago:reply-private-thread",
            kwargs={
                "id": other_user_private_thread.id,
                "slug": other_user_private_thread.slug,
            },
        ),
        {
            PostForm.attachment_ids_field: [str(user_text_attachment.id)],
            PostForm.delete_attachment_field: str(user_text_attachment.id),
            "posting-post-post": "Reply contents",
        },
    )
    assert_contains(response, "Reply to thread")
    assert_contains(response, "misago-editor-attachments=")

    assert_contains_element(
        response,
        "input",
        type="hidden",
        name=PostForm.attachment_ids_field,
        value=user_text_attachment.id,
    )
    assert_contains_element(
        response,
        "input",
        type="hidden",
        name=PostForm.deleted_attachment_ids_field,
        value=user_text_attachment.id,
    )
    assert_not_contains(response, user_text_attachment.name)
    assert_not_contains(response, user_text_attachment.get_absolute_url())


@pytest.mark.parametrize(
    "action_name", (PostingFormset.preview_action, PostForm.upload_action)
)
def test_reply_private_thread_view_maintains_deleted_attachments_list(
    action_name, user_client, other_user_private_thread, user_text_attachment
):
    response = user_client.post(
        reverse(
            "misago:reply-private-thread",
            kwargs={
                "id": other_user_private_thread.id,
                "slug": other_user_private_thread.slug,
            },
        ),
        {
            action_name: "true",
            PostForm.attachment_ids_field: [str(user_text_attachment.id)],
            PostForm.deleted_attachment_ids_field: [str(user_text_attachment.id)],
            "posting-post-post": "Reply contents",
        },
    )
    assert_contains(response, "Reply to thread")
    assert_contains(response, "misago-editor-attachments=")

    assert_contains_element(
        response,
        "input",
        type="hidden",
        name=PostForm.attachment_ids_field,
        value=user_text_attachment.id,
    )
    assert_contains_element(
        response,
        "input",
        type="hidden",
        name=PostForm.deleted_attachment_ids_field,
        value=user_text_attachment.id,
    )
    assert_not_contains(response, user_text_attachment.name)
    assert_not_contains(response, user_text_attachment.get_absolute_url())


def test_reply_private_thread_view_deletes_attachment_on_submit(
    user_client, other_user_private_thread, user_text_attachment
):
    response = user_client.post(
        reverse(
            "misago:reply-private-thread",
            kwargs={
                "id": other_user_private_thread.id,
                "slug": other_user_private_thread.slug,
            },
        ),
        {
            PostForm.attachment_ids_field: [str(user_text_attachment.id)],
            PostForm.deleted_attachment_ids_field: [str(user_text_attachment.id)],
            "posting-title-title": "Hello world",
            "posting-post-post": "How's going?",
        },
    )
    assert response.status_code == 302

    other_user_private_thread.refresh_from_db()
    assert (
        response["location"]
        == reverse(
            "misago:private-thread",
            kwargs={
                "id": other_user_private_thread.id,
                "slug": other_user_private_thread.slug,
            },
        )
        + f"#post-{other_user_private_thread.last_post_id}"
    )

    user_text_attachment.refresh_from_db()
    assert user_text_attachment.category_id is None
    assert user_text_attachment.thread_id is None
    assert user_text_attachment.post_id is None
    assert user_text_attachment.is_deleted


def test_reply_private_thread_view_embeds_attachments_in_preview(
    user_client, other_user_private_thread, user_image_attachment
):
    response = user_client.post(
        reverse(
            "misago:reply-private-thread",
            kwargs={
                "id": other_user_private_thread.id,
                "slug": other_user_private_thread.slug,
            },
        ),
        {
            PostingFormset.preview_action: "true",
            PostForm.attachment_ids_field: [str(user_image_attachment.id)],
            "posting-post-post": (
                f"Attachment: <attachment={user_image_attachment.name}:{user_image_attachment.id}>"
            ),
        },
    )
    assert_contains(response, "Reply to thread")
    assert_contains(response, "Message preview")
    assert_contains_element(response, "a", href=user_image_attachment.get_details_url())
    assert_contains_element(
        response, "img", src=user_image_attachment.get_absolute_url()
    )
