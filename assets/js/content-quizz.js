// to handle a new type of answer, you just need to create a method called
// initializeXXX(answers) that will add the reset the field content and mark good answer
// then add the two methods in the callback lists

let index = 0

function extractAnswer(radio, answers) {
  radio.forEach((rb) => {
    if (!rb.parentElement.parentElement.getAttribute('id')) {
      rb.parentElement.parentElement.setAttribute('id', 'id-' + (index++))
    }
    rb.setAttribute('name', rb.parentElement.parentElement.getAttribute('id'))
    rb.parentElement.parentElement.parentElement.parentElement.setAttribute('data-name', rb.getAttribute('name'))
    if (!answers[rb.parentNode.parentNode.getAttribute('id')]) {
      answers[rb.parentNode.parentNode.getAttribute('id')] = [rb.checked]
    } else {
      answers[rb.parentNode.parentNode.getAttribute('id')].push(rb.checked)
    }
    rb.setAttribute('value', answers[rb.parentNode.parentNode.getAttribute('id')].length - 1)
    rb.disabled = false
    rb.checked = false
  })
}

function initializeCheckboxes(answers, blockIds) {
  const checkboxes = document.querySelectorAll('.quizz ul li input[type=checkbox]')
  extractAnswer(checkboxes, answers, blockIds)
}


function initializeRadio(answers, blockIds) {
  const radio = document.querySelectorAll('.quizz ul li input[type=radio]')
  extractAnswer(radio, answers, blockIds)
}

const initializePipeline = [initializeCheckboxes, initializeRadio]

function computeForm(formdata, answers) {
  const badAnswers = []
  for (const entry of formdata.entries()) {
    const name = entry[0]
    const values = parseInt(entry[1], 10)
    if (!answers[name]) {
      continue
    } else {
      // first version of quizz only deal with lists
      if (!answers[name][values]) {
        badAnswers.push({
          name: name,
          value: values
        })
      }
    }
  }
  return badAnswers
}

function markBadAnswers(names, answers) {
  const toAdd = []
  if (names.length === 0) {
    Object.keys(answers).forEach(answer => {
      let mustMarkBad = false
      answers[answer].forEach((value, index) => {
        const inputAnswer = document.querySelector(`#${answer} input[value="${index}"]`)
        if (value && !inputAnswer.checked) {
          inputAnswer.parentElement.classList.add('quizz-forget')
          mustMarkBad = true
        }
      })
      if (mustMarkBad) {
        document.querySelector(`div[data-name="${answer}"]`).classList.add('quizz-bad')
      }
    })
  }
  names.forEach(({ name }) => {
    document.querySelectorAll('input[name="' + name + '"]').forEach(field => {
      if (answers[name][parseInt(field.getAttribute('value'), 10)] && !field.checked) {
        field.parentElement.classList.add('quizz-forget')
        toAdd.push({
          name: name,
          value: field.getAttribute('value')
        })
      }
    })
    document.querySelector(`.custom-block[data-name=${name}]`).classList.add('quizz-bad')
  })
  names.forEach(({
    name,
    value
  }) => {
    document.querySelector(`input[type=checkbox][name="${name}"][value="${value}"]`)
      .parentElement.classList.add('quizz-bad')
  })
  toAdd.forEach(name => names.push(name))
}

function getWantedHeading(questionNode, nodeName, attr) {
  let potentialHeading = questionNode
  while (potentialHeading[attr] &&
  potentialHeading.nodeName !== nodeName.toUpperCase()) {
    potentialHeading = potentialHeading[attr]
  }
  if (potentialHeading.nodeName !== nodeName.toUpperCase()) {
    return null
  }
  return potentialHeading
}

function injectForms(quizz, answers) {
  const searchedTitle = quizz.getAttribute('data-heading-level') || 'h3'
  const submitLabel = quizz.getAttribute('data-quizz-validate') || 'Validate'
  const headings = {}
  let idBias = 0
  Object.keys(answers).forEach(blockId => {
    const questionNode = document.getElementById(blockId).parentElement.parentElement
    const heading = getWantedHeading(questionNode, searchedTitle, 'previousSibling') || quizz
    if (!heading.getAttribute('id')) {
      console.log('new id')
      heading.setAttribute('id', `quizz-form-${idBias}`)
      idBias++
    }
    console.log(headings)
    console.log(heading.getAttribute('id'))
    if (heading && !headings[heading.getAttribute('id')]) {
      headings[heading.getAttribute('id')] = true
      const form = document.createElement('form')
      form.classList.add('quizz')
      quizz.appendChild(form)

      const submit = document.createElement('button')
      submit.innerText = submitLabel
      submit.classList.add('btn-submit')
      submit.classList.add('btn')
      const result = document.createElement('p')
      result.classList.add('result')
     let nodeToAddToForm = heading
      if (heading === quizz) {
        nodeToAddToForm = quizz.firstChild
        nodeToAddToForm.parentNode.removeChild(nodeToAddToForm)
        form.appendChild(nodeToAddToForm)
      } else {
        nodeToAddToForm = heading.nextSibling
      }
      form.method = 'POST'
      form.setAttribute('action', quizz.getAttribute('data-answer-url'))

      while (nodeToAddToForm && nodeToAddToForm.nodeName !== searchedTitle.toUpperCase()) {
        const current = nodeToAddToForm
        nodeToAddToForm = nodeToAddToForm.nextSibling
        form.appendChild(current.cloneNode(true))
        current.parentNode.removeChild(current)
      }
      form.appendChild(result)
      form.appendChild(submit)
      console.log('append form')
      if (heading === quizz) {
        quizz.appendChild(form)
      } else {
        quizz.insertBefore(form, heading.nextSibling)
      }
    }
  })
}

const answers = {}
initializePipeline.forEach(func => func(answers))
document.querySelectorAll('div.quizz').forEach(div => {
  injectForms(div, answers)
})
document.querySelectorAll('form.quizz').forEach(form => {
  form.addEventListener('submit', e => {
    e.preventDefault()
    e.stopPropagation()
    const formData = new FormData(form)
    // result = name of bad answers
    const result = computeForm(formData, answers)
    markBadAnswers(result, answers)
    const questions = []
    result.forEach(result => {
      if (questions.indexOf(result.name) === -1) {
        questions.push(result.name)
      }
    })
    const statistics = {
      expected: {},
      result: {}
    }
    let nbGood = 0
    let nbTotal = 0
    Object.keys(answers).forEach(name => {
      const element = document.querySelector(`.custom-block[data-name="${name}"]`)
      const title = element.querySelector('.custom-block-heading').textContent
      const correction = element.querySelector('.custom-block .custom-block .custom-block-heading')

      statistics.result[title] = {
        evaluation: 'bad',
        labels: []
      }
      statistics.expected[title] = {}
      const availableResponses = element.querySelectorAll('input')
      for (let i = 0; i < availableResponses.length; i++) {
        let responseText = availableResponses[i].parentElement.textContent
        if (i === availableResponses.length - 1 && correction && responseText.indexOf(correction.textContent) !== -1) {
          responseText = responseText.substr(0, responseText.indexOf(correction.textContent))
        }
        statistics.expected[title][responseText] = answers[name][i]
      }
      element.querySelectorAll('input:checked')
        .forEach(node => {
          let label = node.parentElement.textContent
          if (correction && label.indexOf(correction.textContent) !== -1) {
            label = label.substr(0, label.indexOf(correction.textContent))
          }
          statistics.result[title].labels.push(label.trim())
        })
      nbTotal++
      if (!element.classList.contains('quizz-bad') && !element.classList.contains('quizz-forget')) {
        element.classList.add('quizz-good')
        statistics.result[title].evaluation = 'ok'
        nbGood++
      }
    })
    const csrfmiddlewaretoken = document.querySelector('input[name=\'csrfmiddlewaretoken\']').value
    const xhttp = new XMLHttpRequest()
    xhttp.open('POST', form.getAttribute('action'))
    xhttp.setRequestHeader('X-Requested-With', 'XMLHttpRequest')
    xhttp.setRequestHeader('Content-Type', 'application/json')
    xhttp.setRequestHeader('X-CSRFToken', csrfmiddlewaretoken)
    statistics.url = form.parentElement.previousElementSibling.firstElementChild.href
    xhttp.send(JSON.stringify(statistics))
    const percentOfAnswers = (100 * 1.0 * nbGood / nbTotal).toLocaleString('fr-FR', {
      minimumIntegerDigits: 1,
      useGrouping: false
    })
    form.querySelector('.result').innerText = `Vous avez bien répondu à ${percentOfAnswers}% des questions.`
  })
})
