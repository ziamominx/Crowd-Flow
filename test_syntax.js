const fs = require('fs');
const html = fs.readFileSync('concourse.html', 'utf8');
const match = html.match(/<script type="text\/babel">([\s\S]*?)<\/script>/);
if (!match) {
  console.log('No babel script tag found');
  process.exit(1);
}
fs.writeFileSync('extracted_script.jsx', match[1]);
console.log('Extracted', match[1].length, 'characters of JSX');
