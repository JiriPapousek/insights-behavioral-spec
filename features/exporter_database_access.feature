Feature: Ability to access database

  Background: System is in default state and database exist
    Given the system is in default state
      And the database is named test
      And database user is set to postgres
      And database password is set to postgres

  Scenario: Check access to empty database
     When database connection is established
     Then I should find that the database is empty

  Scenario: Check table creatinon on deletion
     When database connection is established
     Then the database is empty
     When I prepare database schema
     Then I should find that all tables are empty
     When I delete all tables from database
     Then I should find that the database is empty
