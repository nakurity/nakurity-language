// main.js

class ArgumentParser {
  constructor(args) {
    this.args = args.slice(1); // Skip the command nakurity
  }

  getFilename() {
    return this.args[0]; // First argument after the script name
  }
}

function _runner(filename) {
  // You can add your custom logic here
  console.log(`Running with file: ${filename}`);
}

const parser = new ArgumentParser(process.argv);
const filename = parser.getFilename();

if (filename) {
  _runner(filename);
} else {
  console.error(`No filename provided. Usage: ${process.argv[0]} <filename>`);
}
