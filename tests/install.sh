set -e

# Python dependencies
pip install flake8 json-merge-patch jsonschema "pytest<3" requests

# Ruby dependencies
curl -s -S -o /tmp/Gemfile $BASEDIR/fixtures/Gemfile
gem install bundler
bundle install --gemfile=/tmp/Gemfile --path /tmp/vendor/bundle --binstubs=/tmp/bin
