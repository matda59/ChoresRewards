# Quiz questions for the daily bonus quiz (ages 4–8)
# Each question can be of type: 'animal_image', 'animal_sound', 'landmark', or 'fact'.
# For 'animal_image' and 'landmark', use a static image path. For 'animal_sound', use a static sound path.
# For 'fact', just show the fact and a simple true/false or multiple choice.

quiz_questions = [
    {
        'type': 'animal_image',
        'question': 'What animal is this?',
        'image': '/static/images/elephant.jpg',
        'choices': ['Elephant', 'Lion', 'Giraffe', 'Dog'],
        'answer': 'Elephant',
        'difficulty': 'complex'
    },
    {
        'type': 'animal_sound',
        'question': 'Which animal makes this sound?',
        'sound': '/static/sounds/lion-roar.mp3',
        'choices': [
            '/static/images/Lion.jpg',
            '/static/images/Cow.jpg',
            '/static/images/Sheep_in_field_(Unsplash).jpg',
            '/static/images/Pig_looking_up.jpg'
        ],
        'answer': '/static/images/Lion.jpg',
        'difficulty': 'easy'
    },
    {
        'type': 'landmark',
        'question': 'What is the name of this famous place?',
        'image': '/static/images/eiffel_tower.jpg',
        'choices': ['Eiffel Tower', 'Big Ben', 'Statue of Liberty', 'Colosseum'],
        'answer': 'Eiffel Tower',
        'difficulty': 'complex'
    },
    {
        'type': 'fact',
        'question': 'True or False: Penguins can fly.',
        'choices': ['True', 'False'],
        'answer': 'False',
        'difficulty': 'complex'
    },
    {
        'type': 'animal_image',
        'question': 'What animal is this?',
        'image': '/static/images/kangaroo.jpg',
        'choices': ['Kangaroo', 'Horse', 'Deer', 'Dog'],
        'answer': 'Kangaroo',
        'difficulty': 'complex'
    },
    {
        'type': 'landmark',
        'question': 'Where is this landmark located?',
        'image': '/static/images/statue_of_liberty.jpg',
        'choices': ['New York', 'Paris', 'London', 'Rome'],
        'answer': 'New York',
        'difficulty': 'complex'
    },
    {
        'type': 'fact',
        'question': 'Which is the largest planet in our solar system?',
        'choices': ['Earth', 'Mars', 'Jupiter', 'Venus'],
        'answer': 'Jupiter',
        'difficulty': 'complex'
    },
    {
        'type': 'animal_sound',
        'question': 'Which animal makes this sound?',
        'sound': '/static/sounds/duck-quack.mp3',
        'choices': [
            '/static/images/Mallard2.jpg',
            '/static/images/cow.jpg',
            '/static/images/Sheep_in_field_(Unsplash).jpg',
            '/static/images/Pig_looking_up.jpg'
        ],
        'answer': '/static/images/Mallard2.jpg',
        'difficulty': 'easy'
    },
    {
        'type': 'animal_image',
        'question': 'What animal is this?',
        'image': '/static/images/giraffe.jpg',
        'choices': ['Giraffe', 'Horse', 'Zebra', 'Lion'],
        'answer': 'Giraffe',
        'difficulty': 'complex'
    },
    {
        'type': 'animal_image',
        'question': 'What animal is this?',
        'image': '/static/images/panda.jpg',
        'choices': ['Panda', 'Bear', 'Koala', 'Monkey'],
        'answer': 'Panda',
        'difficulty': 'complex'
    },
    {
        'type': 'animal_image',
        'question': 'What animal is this?',
        'image': '/static/images/tiger.jpg',
        'choices': ['Tiger', 'Lion', 'Leopard', 'Cheetah'],
        'answer': 'Tiger',
        'difficulty': 'complex'
    },
    {
        'type': 'animal_image',
        'question': 'What animal is this?',
        'image': '/static/images/koala.jpg',
        'choices': ['Koala', 'Panda', 'Bear', 'Monkey'],
        'answer': 'Koala',
        'difficulty': 'complex'
    },
    {
        'type': 'animal_sound',
        'question': 'Which animal makes this sound?',
        'sound': '/static/sounds/cow-moo.mp3',
        'choices': [
            '/static/images/Cow.jpg',
            '/static/images/horse.jpg',
            '/static/images/Sheep_in_field_(Unsplash).jpg',
            '/static/images/Pig_looking_up.jpg'
        ],
        'answer': '/static/images/Cow.jpg',
        'difficulty': 'easy'
    },
    {
        'type': 'animal_sound',
        'question': 'Which animal makes this sound?',
        'sound': '/static/sounds/elephant-trumpet.mp3',
        'choices': [
            '/static/images/elephant.jpg',
            '/static/images/Lion.jpg',
            '/static/images/monkey.jpg',
            '/static/images/tiger.jpg'
        ],
        'answer': '/static/images/elephant.jpg',
        'difficulty': 'easy'
    },
    {
        'type': 'animal_sound',
        'question': 'Which animal makes this sound?',
        'sound': '/static/sounds/sheep-baa.mp3',
        'choices': [
            '/static/images/Sheep_in_field_(Unsplash).jpg',
            '/static/images/goat.jpg',
            '/static/images/Cow.jpg',
            '/static/images/dog.JPG'
        ],
        'answer': '/static/images/Sheep_in_field_(Unsplash).jpg',
        'difficulty': 'easy'
    },
    {
        'type': 'animal_sound',
        'question': 'Which animal makes this sound?',
        'sound': '/static/sounds/horse-neigh.mp3',
        'choices': [
            '/static/images/horse.jpg',
            '/static/images/Cow.jpg',
            '/static/images/dog.JPG',
            '/static/images/Sheep_in_field_(Unsplash).jpg'
        ],
        'answer': '/static/images/horse.jpg',
        'difficulty': 'easy'
    },
    {
        'type': 'animal_sound',
        'question': 'Which animal makes this sound?',
        'sound': '/static/sounds/frog-croak.mp3',
        'choices': [
            '/static/images/frog.jpg',
            '/static/images/monkey.jpg',
            '/static/images/A-Cat.jpg',
            '/static/images/dog.JPG'
        ],
        'answer': '/static/images/frog.jpg',
        'difficulty': 'easy'
    },
    {
        'type': 'animal_sound',
        'question': 'Which animal makes this sound?',
        'sound': '/static/sounds/owl-hoot.mp3',
        'choices': [
            '/static/images/Barred_Owl_on_branch.jpg',
            '/static/images/stickers-american-bald-eagle-on-tree.jpg.jpg',
            '/static/images/chicken.jpg',
            '/static/images/rooster.jpg'
        ],
        'answer': '/static/images/Barred_Owl_on_branch.jpg',
        'difficulty': 'easy'
    },
    {
        'type': 'animal_sound',
        'question': 'Which animal makes this sound?',
        'sound': '/static/sounds/monkey-chatter.mp3',
        'choices': [
            '/static/images/monkey.jpg',
            '/static/images/panda.jpg',
            '/static/images/A-Cat.jpg',
            '/static/images/koala.jpg'
        ],
        'answer': '/static/images/monkey.jpg',
        'difficulty': 'easy'
    },
    {
        'type': 'animal_sound',
        'question': 'Which animal makes this sound?',
        'sound': '/static/sounds/dolphin-click.mp3',
        'choices': [
            '/static/images/Common_dolphin_noaa.jpg',
            '/static/images/Hawaii_humpback_SusanPatriciaLeonard123rf.webp',
            '/static/images/frog.jpg',
            '/static/images/Pig_looking_up.jpg'
        ],
        'answer': '/static/images/Common_dolphin_noaa.jpg',
        'difficulty': 'easy'
    },
    {
        'type': 'animal_sound',
        'question': 'Which animal makes this sound?',
        'sound': '/static/sounds/rooster-crow.mp3',
        'choices': [
            '/static/images/rooster.jpg',
            '/static/images/chicken.jpg',
            '/static/images/Lion.jpg',
            '/static/images/Pig_looking_up.jpg'
        ],
        'answer': '/static/images/rooster.jpg',
        'difficulty': 'easy'
    },
    {
        'type': 'animal_sound',
        'question': 'Which animal makes this sound?',
        'sound': '/static/sounds/pig-oink.mp3',
        'choices': [
            '/static/images/Pig_looking_up.jpg',
            '/static/images/Cow.jpg',
            '/static/images/Lion.jpg',
            '/static/images/Sheep_in_field_(Unsplash).jpg'
        ],
        'answer': '/static/images/Pig_looking_up.jpg',
        'difficulty': 'easy'
    },
    {
        'type': 'landmark',
        'question': 'What is the name of this famous place?',
        'image': '/static/images/pyramid.jpg',
        'choices': ['Pyramids of Giza', 'Eiffel Tower', 'Great Wall', 'Colosseum'],
        'answer': 'Pyramids of Giza',
        'difficulty': 'complex'
    },
    {
        'type': 'landmark',
        'question': 'What is the name of this famous place?',
        'image': '/static/images/great_wall.jpg',
        'choices': ['Great Wall of China', 'Eiffel Tower', 'Statue of Liberty', 'Sydney Opera House'],
        'answer': 'Great Wall of China',
        'difficulty': 'complex'
    },
    {
        'type': 'landmark',
        'question': 'What is the name of this famous place?',
        'image': '/static/images/sydney_opera_house.jpg',
        'choices': ['Sydney Opera House', 'Eiffel Tower', 'Colosseum', 'Big Ben'],
        'answer': 'Sydney Opera House',
        'difficulty': 'complex'
    },
    {
        'type': 'landmark',
        'question': 'What is the name of this famous place?',
        'image': '/static/images/mount_fuji.jpg',
        'choices': ['Mount Fuji', 'Mount Everest', 'Mount Rushmore', 'Matterhorn'],
        'answer': 'Mount Fuji',
        'difficulty': 'complex'
    },
    {
        'type': 'landmark',
        'question': 'What is the name of this famous place?',
        'image': '/static/images/leaning_tower_pisa.jpg',
        'choices': ['Leaning Tower of Pisa', 'Eiffel Tower', 'Big Ben', 'Space Needle'],
        'answer': 'Leaning Tower of Pisa',
        'difficulty': 'complex'
    },
    {
        'type': 'landmark',
        'question': 'What is the name of this famous place?',
        'image': '/static/images/colosseum.jpg',
        'choices': ['Colosseum', 'Pantheon', 'Acropolis', 'Stonehenge'],
        'answer': 'Colosseum',
        'difficulty': 'complex'
    },
    {
        'type': 'fact',
        'question': 'True or False: Fish can breathe underwater.',
        'choices': ['True', 'False'],
        'answer': 'True',
        'difficulty': 'complex'
    },
    {
        'type': 'fact',
        'question': 'Which planet is known as the Red Planet?',
        'choices': ['Venus', 'Mars', 'Jupiter', 'Saturn'],
        'answer': 'Mars',
        'difficulty': 'complex'
    },
    {
        'type': 'fact',
        'question': 'True or False: The sun is a star.',
        'choices': ['True', 'False'],
        'answer': 'True',
        'difficulty': 'complex'
    },
    {
        'type': 'fact',
        'question': 'Which is the largest land animal?',
        'choices': ['Elephant', 'Giraffe', 'Lion', 'Bear'],
        'answer': 'Elephant',
        'difficulty': 'complex'
    },
    {
        'type': 'fact',
        'question': 'Which is the fastest land animal?',
        'choices': ['Cheetah', 'Lion', 'Horse', 'Tiger'],
        'answer': 'Cheetah',
        'difficulty': 'complex'
    },
    {
        'type': 'fact',
        'question': 'True or False: Spiders are insects.',
        'choices': ['True', 'False'],
        'answer': 'False',
        'difficulty': 'complex'
    },
    {
        'type': 'fact',
        'question': 'Which bird has the most colorful feathers?',
        'choices': ['Peacock', 'Duck', 'Owl', 'Chicken'],
        'answer': 'Peacock',
        'difficulty': 'complex'
    },
    {
        'type': 'fact',
        'question': 'Which fruit is yellow and curved?',
        'choices': ['Banana', 'Apple', 'Grape', 'Orange'],
        'answer': 'Banana',
        'difficulty': 'complex'
    },
    {
        'type': 'fact',
        'question': 'True or False: Alligators and crocodiles are the same.',
        'choices': ['True', 'False'],
        'answer': 'False',
        'difficulty': 'complex'
    },
    {
        'type': 'fact',
        'question': 'Which insect makes honey?',
        'choices': ['Bee', 'Ant', 'Butterfly', 'Spider'],
        'answer': 'Bee',
        'difficulty': 'complex'
    },
    {
        'type': 'math',
        'question': 'What is 7 × 8?',
        'choices': ['54', '56', '64', '48'],
        'answer': '56',
        'difficulty': 'complex'
    },
    {
        'type': 'math',
        'question': 'What is 9 × 6?',
        'choices': ['54', '56', '48', '63'],
        'answer': '54',
        'difficulty': 'complex'
    },
    {
        'type': 'math',
        'question': 'What is 45 + 27?',
        'choices': ['72', '82', '62', '71'],
        'answer': '72',
        'difficulty': 'complex'
    },
    {
        'type': 'math',
        'question': 'What is 83 - 26?',
        'choices': ['57', '67', '53', '59'],
        'answer': '57',
        'difficulty': 'complex'
    },
    {
        'type': 'math',
        'question': 'What is 12 × 4?',
        'choices': ['48', '44', '52', '46'],
        'answer': '48',
        'difficulty': 'complex'
    },
    {
        'type': 'math',
        'question': 'What is 64 ÷ 8?',
        'choices': ['8', '7', '9', '6'],
        'answer': '8',
        'difficulty': 'complex'
    },
    {
        'type': 'math',
        'question': 'What is 72 ÷ 9?',
        'choices': ['8', '9', '7', '6'],
        'answer': '8',
        'difficulty': 'complex'
    },
    {
        'type': 'math',
        'question': 'What is 35 + 49?',
        'choices': ['84', '74', '94', '86'],
        'answer': '84',
        'difficulty': 'complex'
    },
    {
        'type': 'math',
        'question': 'What is 91 - 37?',
        'choices': ['54', '64', '44', '56'],
        'answer': '54',
        'difficulty': 'complex'
    },
    {
        'type': 'problem_solving',
        'question': 'Sarah has 24 stickers. She gives 8 to her friend and buys 15 more. How many stickers does she have now?',
        'choices': ['31', '29', '33', '27'],
        'answer': '31',
        'difficulty': 'complex'
    },
    {
        'type': 'problem_solving',
        'question': 'A box holds 6 apples. How many apples are in 7 boxes?',
        'choices': ['42', '36', '48', '40'],
        'answer': '42',
        'difficulty': 'complex'
    },
    {
        'type': 'problem_solving',
        'question': 'Tom reads 3 pages every day. How many pages will he read in 2 weeks?',
        'choices': ['42', '21', '35', '28'],
        'answer': '42',
        'difficulty': 'complex'
    },
    {
        'type': 'problem_solving',
        'question': 'A train has 8 cars. Each car has 12 seats. How many seats are there in total?',
        'choices': ['96', '84', '108', '92'],
        'answer': '96',
        'difficulty': 'complex'
    },
    {
        'type': 'problem_solving',
        'question': 'Emma collects 56 shells at the beach. She gives away 18 shells. How many shells does she keep?',
        'choices': ['38', '42', '34', '40'],
        'answer': '38',
        'difficulty': 'complex'
    },
    {
        'type': 'problem_solving',
        'question': 'If you save $5 every week, how much money will you have after 8 weeks?',
        'choices': ['$40', '$35', '$45', '$30'],
        'answer': '$40',
        'difficulty': 'complex'
    },
    {
        'type': 'math',
        'question': 'What is 6 × 7?',
        'choices': ['42', '48', '36', '40'],
        'answer': '42',
        'difficulty': 'complex'
    },
    {
        'type': 'math',
        'question': 'What is 56 ÷ 7?',
        'choices': ['8', '7', '9', '6'],
        'answer': '8',
        'difficulty': 'complex'
    },
    {
        'type': 'problem_solving',
        'question': 'A pizza is cut into 8 slices. If 3 people each eat 2 slices, how many slices are left?',
        'choices': ['2', '3', '1', '4'],
        'answer': '2',
        'difficulty': 'complex'
    },
    {
        'type': 'problem_solving',
        'question': 'Lucy has 36 marbles. She puts them into bags with 9 marbles each. How many bags does she need?',
        'choices': ['4', '5', '3', '6'],
        'answer': '4',
        'difficulty': 'complex'
    }
]
