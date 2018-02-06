# TODO: Add script to assign authors of contacts (or people responsible for a country) to:

[
  Contact.joins("LEFT JOIN addresses ON addressable_id = contacts.id").where('country_code IS NULL OR country_code = ""'),
  Contact.people.where(company: '').where('author_id IS NOT NULL AND author_id != ""')
