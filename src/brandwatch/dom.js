() => {
  const text = document.body?.innerText || '';
  const links = Array.from(document.querySelectorAll('a[href]'));
  const forms = Array.from(document.forms);
  return {
    title: document.title.slice(0, 512),
    text: text.slice(0, 20000),
    links: links.slice(0, 100).map(a => ({
      text: a.innerText.slice(0, 200), url: a.href.slice(0, 2048)
    })),
    forms: forms.slice(0, 20).map(form => ({
      action: form.action.slice(0, 2048),
      method: form.method.toUpperCase(),
      fields: Array.from(form.elements).slice(0, 20).map(field => ({
        tag: field.tagName.toLowerCase(),
        type: (field.type || '').slice(0, 40),
        name: (field.name || '').slice(0, 100)
      })),
      fields_truncated: form.elements.length > 20
    })),
    iframe_count: document.querySelectorAll('iframe').length,
    truncated: {text: text.length > 20000, links: links.length > 100, forms: forms.length > 20}
  };
}
