set -e

# Python dependencies
pip install flake8 "pytest<3"

# Ruby dependencies
curl -s -S -O $BASEDIR/fixtures/Gemfile
gem install bundler
bundle install --path vendor/bundle --binstubs
