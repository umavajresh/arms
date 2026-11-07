(function ($) {
  const LAUNCHER_DISMISSED_KEY = 'arms.assistantLauncherDismissed';

  function readPreference(key) {
    try {
      return window.localStorage.getItem(key);
    } catch (error) {
      return null;
    }
  }

  function writePreference(key, value) {
    try {
      window.localStorage.setItem(key, value);
    } catch (error) {
      return;
    }
  }

  if (readPreference(LAUNCHER_DISMISSED_KEY) === '1') {
    document.documentElement.classList.add('launcher-dismissed');
  }

  const CONTROL_SELECTOR = 'a[href], button, input, select, textarea, label, [role="button"], .seat';

  function launcherOutline(launcher) {
    const box = launcher.getBoundingClientRect();
    const centreX = box.left + box.width / 2;
    const centreY = box.top + box.height / 2;
    const radius = Math.min(box.width, box.height) / 2 + 4;
    const points = [[centreX, centreY]];
    for (let step = 0; step < 16; step += 1) {
      const angle = (step / 16) * 2 * Math.PI;
      points.push([centreX + radius * Math.cos(angle), centreY + radius * Math.sin(angle)]);
    }
    return points;
  }

  function launcherCoversControls(launcher) {
    return launcherOutline(launcher).some(function (point) {
      return document.elementsFromPoint(point[0], point[1]).some(function (element) {
        return !launcher.contains(element) && element.closest(CONTROL_SELECTOR);
      });
    });
  }

  function keepLauncherClearOfControls(launcher) {
    let scheduled = false;
    function update() {
      scheduled = false;
      const focused = launcher.contains(document.activeElement);
      launcher.classList.toggle('is-yielding', !focused && launcherCoversControls(launcher));
    }
    function schedule() {
      if (!scheduled) {
        scheduled = true;
        window.requestAnimationFrame(update);
      }
    }
    window.addEventListener('scroll', schedule, { passive: true });
    window.addEventListener('resize', schedule);
    new MutationObserver(schedule).observe(document.body, { childList: true, subtree: true });
    schedule();
  }

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
    const alertBox = $('<div class="alert alert-danger err-msg" role="alert">').text(message);
    target.prepend(alertBox);
    alertBox[0].scrollIntoView({ block: 'nearest' });
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

  window._conf = function (message = '', handler = '', params = [], confirmLabel = 'Continue') {
    $('#confirm_modal #confirm').text(confirmLabel).attr('onclick', handler + '(' + params.join(',') + ')');
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
    const transientMessages = $('.redirect-msg.alert-success, .redirect-msg.alert-info');
    if (transientMessages.length) {
      setTimeout(function () {
        transientMessages.slideUp(500, function () {
          $(this).remove();
        });
      }, 5000);
    }
    const launcher = document.getElementById('ai-launcher');
    if (launcher) {
      keepLauncherClearOfControls(launcher);
    }
    $('#ai-launcher-dismiss').on('click', function () {
      writePreference(LAUNCHER_DISMISSED_KEY, '1');
      document.documentElement.classList.add('launcher-dismissed');
    });
    $(document).on('submit', 'form[data-route-search]', function (event) {
      const form = $(this);
      const origin = form.find('[name="from_airport"]').val();
      const destination = form.find('[name="to_airport"]').val();
      if (origin && origin === destination) {
        event.preventDefault();
        armsShowFormError(this, 'Origin and destination must be different airports.');
      }
    });
  });
})(jQuery);
