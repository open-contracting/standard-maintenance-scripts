set -e

# Python dependencies
pip install flake8 jsonschema "pytest<3" requests

# Ruby dependencies
curl -s -S -O $BASEDIR/fixtures/Gemfile
gem install bundler
bundle install --path vendor/bundle --binstubs
