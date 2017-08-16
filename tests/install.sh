# Python dependencies
pip install flake8 pytest

# Ruby dependencies
curl -s -O $BASEDIR/fixtures/Gemfile
gem install bundler
bundle install --path vendor/bundle --binstubs
