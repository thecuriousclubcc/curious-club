/*
 * Wakiga online diagnosis - application form.
 *
 * Flow: input -> confirm -> submit -> done.
 * Set FORM_ENDPOINT to a URL that accepts a JSON POST (your own API, a form
 * service, etc.). While it is empty the form runs in demo mode: nothing is
 * sent and the completion screen is shown so the UI can be checked.
 */
;(function () {
  'use strict'

  var FORM_ENDPOINT = ''

  var LABELS = {
    name: 'お名前',
    kana: 'フリガナ',
    birth: '生年月日',
    gender: '性別',
    email: 'メールアドレス',
    tel: '電話番号',
    zip: '郵便番号',
    address: 'ご住所',
    building: '建物名・部屋番号',
    symptoms: '現在の状況',
    history: 'わきがの治療歴',
    date1: '第1希望日',
    time1: '第1希望 時間帯',
    date2: '第2希望日',
    time2: '第2希望 時間帯',
    device: 'ご利用予定の端末',
    message: 'ご質問・ご要望',
  }

  var form = document.getElementById('apply-form')
  var confirmBox = document.getElementById('confirm')
  var confirmList = document.getElementById('confirm-list')
  var doneBox = document.getElementById('done')
  var formError = document.getElementById('form-error')
  var submitError = document.getElementById('submit-error')
  var backBtn = document.getElementById('back-btn')
  var sendBtn = document.getElementById('send-btn')

  // Interview dates must be from tomorrow onward.
  var tomorrow = new Date()
  tomorrow.setDate(tomorrow.getDate() + 1)
  var minDate = toISODate(tomorrow)
  form.querySelectorAll('[data-future]').forEach(function (el) {
    el.min = minDate
  })
  document.getElementById('birth').max = toISODate(new Date())

  function toISODate(d) {
    var m = String(d.getMonth() + 1).padStart(2, '0')
    var day = String(d.getDate()).padStart(2, '0')
    return d.getFullYear() + '-' + m + '-' + day
  }

  function setStep(step) {
    document.querySelectorAll('[data-step-indicator]').forEach(function (li) {
      li.classList.toggle('is-active', li.getAttribute('data-step-indicator') === step)
    })
    form.hidden = step !== 'input'
    confirmBox.hidden = step !== 'confirm'
    doneBox.hidden = step !== 'done'
    document.getElementById('apply').scrollIntoView({ behavior: 'smooth' })
    if (step === 'done') doneBox.focus({ preventScroll: true })
  }

  /* ---------- Validation ---------- */

  function fieldOf(el) {
    return el.closest('.field')
  }

  function clearError(field) {
    if (!field) return
    field.classList.remove('has-error')
    var msg = field.querySelector('.field-error')
    if (msg) msg.remove()
  }

  function showError(field, text) {
    if (!field) return
    field.classList.add('has-error')
    var msg = field.querySelector('.field-error')
    if (!msg) {
      msg = document.createElement('p')
      msg.className = 'field-error'
      field.appendChild(msg)
    }
    msg.textContent = text
  }

  function validateElement(el) {
    var v = el.validity
    if (v.valid && el.dataset.match) {
      var other = form.elements[el.dataset.match]
      if (other && other.value !== el.value) return el.dataset.matchMsg
    }
    if (v.valid) return ''
    if (v.valueMissing) {
      if (el.dataset.requiredMsg) return el.dataset.requiredMsg
      return el.type === 'radio' || el.tagName === 'SELECT' ? '選択してください' : '入力してください'
    }
    if (v.patternMismatch && el.dataset.patternMsg) return el.dataset.patternMsg
    if (v.typeMismatch && el.type === 'email') return 'メールアドレスの形式で入力してください'
    if (v.rangeUnderflow && el.hasAttribute('data-future')) return '明日以降の日付を選択してください'
    if (v.rangeOverflow) return '正しい日付を入力してください'
    return el.validationMessage || '入力内容をご確認ください'
  }

  function validateAll() {
    var firstInvalid = null
    var seenFields = []
    Array.prototype.forEach.call(form.elements, function (el) {
      if (!el.name || el.type === 'submit') return
      var field = fieldOf(el)
      if (seenFields.indexOf(field) !== -1) return // one message per field (radio groups)
      var msg = validateElement(el)
      if (msg) {
        seenFields.push(field)
        showError(field, msg)
        if (!firstInvalid) firstInvalid = el
      } else {
        clearError(field)
      }
    })
    return firstInvalid
  }

  form.addEventListener('input', function (e) {
    var field = fieldOf(e.target)
    if (field && field.classList.contains('has-error') && !validateElement(e.target)) clearError(field)
  })
  form.addEventListener('change', function (e) {
    var field = fieldOf(e.target)
    if (field && field.classList.contains('has-error') && !validateElement(e.target)) clearError(field)
  })

  /* ---------- Collect & confirm ---------- */

  function collect() {
    var fd = new FormData(form)
    var data = {}
    Object.keys(LABELS).forEach(function (key) {
      var values = fd.getAll(key).map(function (v) { return String(v).trim() }).filter(Boolean)
      data[key] = key === 'symptoms' ? values : values[0] || ''
    })
    return data
  }

  function formatValue(key, value) {
    if (Array.isArray(value)) return value.length ? value.join('、') : '（なし）'
    if (!value) return '（未入力）'
    if (/^\d{4}-\d{2}-\d{2}$/.test(value) && (key === 'birth' || key.indexOf('date') === 0)) {
      var p = value.split('-')
      return p[0] + '年' + Number(p[1]) + '月' + Number(p[2]) + '日'
    }
    return value
  }

  function renderConfirm(data) {
    confirmList.textContent = ''
    Object.keys(LABELS).forEach(function (key) {
      // Skip optional second-choice rows when they were left blank.
      if ((key === 'date2' || key === 'time2' || key === 'building') && !data[key]) return
      var row = document.createElement('div')
      var dt = document.createElement('dt')
      var dd = document.createElement('dd')
      dt.textContent = LABELS[key]
      dd.textContent = formatValue(key, data[key])
      row.appendChild(dt)
      row.appendChild(dd)
      confirmList.appendChild(row)
    })
  }

  var pending = null

  form.addEventListener('submit', function (e) {
    e.preventDefault()
    var invalid = validateAll()
    if (invalid) {
      formError.textContent = '入力内容に不備があります。赤字の項目をご確認ください。'
      formError.hidden = false
      invalid.focus()
      return
    }
    formError.hidden = true
    pending = collect()
    renderConfirm(pending)
    setStep('confirm')
  })

  backBtn.addEventListener('click', function () {
    setStep('input')
  })

  /* ---------- Submit ---------- */

  sendBtn.addEventListener('click', function () {
    if (!pending) return
    submitError.hidden = true
    sendBtn.disabled = true
    backBtn.disabled = true
    sendBtn.textContent = '送信中…'

    var payload = Object.assign({}, pending, {
      type: 'wakiga-online-diagnosis',
      submittedAt: new Date().toISOString(),
    })

    var request = FORM_ENDPOINT
      ? fetch(FORM_ENDPOINT, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
          body: JSON.stringify(payload),
        }).then(function (res) {
          if (!res.ok) throw new Error('HTTP ' + res.status)
        })
      : Promise.resolve() // demo mode

    request
      .then(function () {
        form.reset()
        pending = null
        setStep('done')
      })
      .catch(function () {
        submitError.textContent =
          '送信に失敗しました。通信環境をご確認のうえ、もう一度お試しください。'
        submitError.hidden = false
      })
      .then(function () {
        sendBtn.disabled = false
        backBtn.disabled = false
        sendBtn.textContent = '申し込む'
      })
  })
})()
