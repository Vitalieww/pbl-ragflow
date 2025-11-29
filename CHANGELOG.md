# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]
- To add right side eChart buttons for exercise categorization
##[1.1.0.2] - 2025-11-29
- Under the statistics chart, the AI will create a small resume of the progress made.
- Centered some UI elements
- Gave up on efficiency for speed
##[1.1.0.1] - 2025-11-29
- Added a py program to install required libraries

## [1.1.0.0] - 2025-11-29
- Refactored workout extraction method to use a small separate AI with custom instructions for extracting workouts from user messages.
## [1.0.3.1] - 2025-11-07
- Made environment variables be useable
## [1.0.3] - 2025-10-31
- Connected the database storing the data into an JSON (it collects the data into, number of sets, name of the exercose, )
- Implemented an eChart
- Connected the eChart to show the personalized track progress based on your prompt (your number of sets and so on)

## [1.0.2] - 2025-10-25
- Automatic workout data extraction from user input.
- MySQL database integration for storing workout statistics.
- JSON export of workout data for frontend visualization.

## [1.0.1] - 2025-10-17
- Separated the JS code in the special script.js file
- Moved the stylization css code to the style.css
- Added CHANGELOG file

## [1.0.0] - 2025-10-15
- Initial release
- Added main features: Flask API, database connection, OpenAI integration
