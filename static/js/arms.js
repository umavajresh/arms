(function ($) {
  const loader = $('<div>')
    .attr({ id: 'pre-loader', role: 'status', 'aria-live': 'polite' })
    .text('Processing, please wait.');

  window.start_loader = function () {
    $('#pre-loader').remove();
    $('body').append(loader).addClass('loading');
  };

  window.end_loader = function () {
    $('#pre-loader').remove();
    $('body').removeClass('loading');
  };

  window.armsErrorMessage = function (xhr, fallback) {
    const defaultMessage = fallback || 'An error occurred. Please try again.';
    if (!xhr) {
      return defaultMessage;
    }
    const payload = xhr.responseJSON || (function () {
      try {
        return JSON.parse(xhr.responseText);
      } catch (error) {
        return null;
      }
    })();
    return (payload && (payload.msg || payload.message || payload.error)) || defaultMessage;
  };

  window.armsCookie = function (name) {
    const prefix = name + '=';
    const match = (document.cookie || '')
      .split(';')
      .map(function (cookie) { return cookie.trim(); })
      .find(function (cookie) { return cookie.substring(0, prefix.length) === prefix; });
    return match ? decodeURIComponent(match.substring(prefix.length)) : null;
  };

  window.armsCsrfToken = function (form) {
    const field = form ? $(form).find('input[name="csrfmiddlewaretoken"]').val() : null;
    return field || $('meta[name="csrf-token"]').attr('content') || armsCookie('csrftoken');
  };

  window.armsShowFormError = function (form, message) {
    const target = $(form);
    target.find('.err-msg').remove();
    const alertBox = $('<div class="alert alert-danger err-msg">').text(message).hide();
    target.prepend(alertBox);
    alertBox.show('slow');
    $('html, body, .modal').scrollTop(0);
  };

  window.armsPostForm = function (form, url, onSuccess) {
    const target = $(form);
    if (target[0].checkValidity() === false) {
      target[0].reportValidity();
      return;
    }
    target.find('.err-msg').remove();
    start_loader();
    $.ajax({
      url: url,
      data: new FormData(target[0]),
      cache: false,
      contentType: false,
      processData: false,
      method: 'POST',
      dataType: 'json',
      headers: { 'X-CSRFToken': armsCsrfToken(target) },
      error: function (xhr) {
        end_loader();
        armsShowFormError(target, armsErrorMessage(xhr));
      },
      success: function (response) {
        if (response && response.status !== 'failed') {
          onSuccess(response);
          return;
        }
        end_loader();
        armsShowFormError(target, armsErrorMessage({ responseJSON: response }));
      }
    });
  };

  window.armsPostAction = function (url, data, onSuccess) {
    start_loader();
    $.ajax({
      url: url,
      method: 'POST',
      data: data || {},
      dataType: 'json',
      headers: { 'X-CSRFToken': armsCsrfToken() },
      error: function (xhr) {
        end_loader();
        alert(armsErrorMessage(xhr));
      },
      success: function (response) {
        end_loader();
        if (response && response.status === 'success') {
          (onSuccess || function () { location.reload(); })(response);
          return;
        }
        alert(armsErrorMessage({ responseJSON: response }));
      }
    });
  };

  window.uni_modal = function (title = '', url = '', size = '') {
    start_loader();
    $.ajax({
      url: url,
      error: function (xhr) {
        end_loader();
        alert(armsErrorMessage(xhr, 'The requested content could not be loaded. Please try again.'));
      },
      success: function (response) {
        if (!response) {
          end_loader();
          return;
        }
        $('#uni_modal .modal-title').html(title);
        $('#uni_modal .modal-body').html(response);
        const dialog = $('#uni_modal .modal-dialog')
          .removeAttr('class')
          .addClass('modal-dialog modal-dialog-centered');
        dialog.addClass(size || 'modal-md');
        $('#uni_modal').modal({ backdrop: 'static', keyboard: false, focus: true });
        $('#uni_modal').modal('show');
        end_loader();
      }
    });
  };

  window._conf = function (message = '', handler = '', params = []) {
    $('#confirm_modal #confirm').attr('onclick', handler + '(' + params.join(',') + ')');
    $('#confirm_modal .modal-body').html(message);
    $('#confirm_modal').modal('show');
  };

  function applyZoom(step) {
    const current = parseFloat($('#zoom-value').val());
    const next = current + step;
    if (next < 0 || next > 200) {
      return;
    }
    $('#zoom-value').val(next);
    $('#img-viewer img').css('transform', 'scale(' + next / 100 + ')');
  }

  $(function () {
    $('#viewer_modal').on('shown.bs.modal', function () {
      $('#zoom-value').val(100);
      $('#img-viewer img').css('transform', 'scale(1)');
    });
    $('#zoom-plus').on('click', function () {
      applyZoom(10);
    });
    $('#zoom-minus').on('click', function () {
      applyZoom(-10);
    });
    if ($('.redirect-msg').length) {
      setTimeout(function () {
        $('.redirect-msg').slideUp(500, function () {
          $(this).remove();
        });
      }, 3500);
    }
  });
})(jQuery);
