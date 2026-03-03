-- Add category column to income table
ALTER TABLE income ADD COLUMN IF NOT EXISTS category TEXT;
