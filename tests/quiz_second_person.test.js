const assert = require('assert');
const quiz = require('../static/js/quiz.js');

function createDocument() {
    const nodes = new Set();

    function unregister(el) {
        nodes.delete(el);
        (el.children || []).forEach(unregister);
    }

    function createElement(tag) {
        const el = {
            tagName: tag,
            id: '',
            textContent: '',
            src: '',
            alt: '',
            style: {},
            children: [],
            parent: null,
            onclick: null,
            appendChild(child) {
                child.parent = el;
                el.children.push(child);
                nodes.add(child);
                return child;
            },
            remove() {
                if (el.parent) {
                    el.parent.children = el.parent.children.filter((child) => child !== el);
                }
                unregister(el);
                el.parent = null;
            },
            addEventListener() {},
            querySelector(selector) {
                const id = String(selector).replace(/^#/, '');
                const found = [];
                (function walk(node) {
                    node.children.forEach((child) => {
                        if (child.id === id) found.push(child);
                        walk(child);
                    });
                })(el);
                return found[0] || null;
            }
        };
        Object.defineProperty(el, 'innerHTML', {
            set(html) {
                el.children.forEach(unregister);
                el.children = [];
                const tagRe = /<([a-zA-Z0-9]+)([^>]*)>/g;
                let match;
                while ((match = tagRe.exec(String(html)))) {
                    const child = createElement(match[1]);
                    const idMatch = match[2].match(/\bid="([^"]+)"/);
                    if (idMatch) child.id = idMatch[1];
                    el.appendChild(child);
                }
            }
        });
        nodes.add(el);
        return el;
    }

    const body = createElement('body');
    body.removeChild = (child) => child.remove();

    return {
        createElement,
        getElementById(id) {
            for (const el of nodes) {
                if (el.id === id) return el;
            }
            return null;
        },
        body
    };
}

function installBrowser() {
    global.document = createDocument();
    global.window = {
        quiz_questions: [
            {
                question: 'What is 2 + 2?',
                choices: ['4', '5'],
                answer: '4',
                difficulty: 'complex',
                type: 'fact'
            }
        ],
        person_ages: { 1: 8, 2: 9 }
    };
}

installBrowser();

const firstResults = [];
quiz.showQuizModal(1, (correct, skipped) => firstResults.push({ correct, skipped }));
assert.strictEqual(document.getElementById('quiz-question').textContent, 'What is 2 + 2?');
assert.strictEqual(document.getElementById('quiz-choices').children.length, 2);
assert.strictEqual(firstResults.length, 0, 'opening the quiz must not award bonus points yet');

document.getElementById('quiz-choices').children[0].onclick();
assert.strictEqual(firstResults.length, 1);

const secondResults = [];
quiz.showQuizModal(2, (correct, skipped) => secondResults.push({ correct, skipped }));
assert.ok(document.getElementById('quiz-modal'), 'second person should get a quiz modal');
assert.strictEqual(document.getElementById('quiz-question').textContent, 'What is 2 + 2?');
assert.strictEqual(document.getElementById('quiz-choices').children.length, 2);
assert.strictEqual(secondResults.length, 0, 'second person should answer the quiz before bonus points');

document.getElementById('quiz-choices').children[0].onclick();
assert.strictEqual(secondResults.length, 1);

console.log('quiz_second_person.test.js ok');
